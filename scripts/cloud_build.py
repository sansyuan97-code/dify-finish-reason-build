"""Fixed public-source build. --check performs no Docker or network calls."""
from pathlib import Path, PurePosixPath
import argparse, hashlib, json, os, shutil, stat, subprocess, sys, time, tarfile

SOURCE_SHA='08baec49734f7da83456f64f88c95460385c908e32d9e43d9cbcc8ed33b13447'
COMMIT='8387590ace4a094de812b7847fc6a4c3a27cd52b'
NODE='docker-image://node@sha256:e67514e5d0f6c46656005e1b693b2ec9d52e80b641307de684d4a015ba7a4eaf'
BUILDKIT='moby/buildkit@sha256:cec9f139f45e93c5c69c60f8b07cfad9f43f4ef6b6a6cd917527fea5ff2e3dea'
EXPECTED_REPO='sansyuan97-code/dify-finish-reason-build'
GIB=1024**3

def source_check(archive):
    assert hashlib.sha256(archive.read_bytes()).hexdigest()==SOURCE_SHA,'source hash mismatch'
    with tarfile.open(archive,'r:xz') as z:
        items=z.getmembers()
        assert len(items)==8902 and sum(i.size for i in items)<512*1024**2
        names=set()
        for item in items:
            path=PurePosixPath(item.name)
            assert not path.is_absolute() and '..' not in path.parts and '\\' not in item.name
            assert path.parts and ':' not in path.parts[0] and item.name not in names
            assert item.isfile() and not item.issym() and not item.islnk()
            names.add(item.name)
        assert 'pnpm build && pnpm build:vinext' in z.extractfile('web/Dockerfile').read().decode()
        assert "variable: 'finish_reason'" in z.extractfile('web/app/components/workflow/constants.ts').read().decode()
    return {'source_sha256':SOURCE_SHA,'files':8902,'docker_or_network_used':False,'full_build_passed':False}

def command(args, **kwargs):
    return subprocess.run(args,check=True,**kwargs)

def execute(root):
    assert sys.platform=='linux' and os.environ.get('GITHUB_ACTIONS')=='true'
    assert os.environ.get('GITHUB_REPOSITORY')==EXPECTED_REPO
    assert os.environ.get('GITHUB_EVENT_NAME')=='workflow_dispatch'
    assert os.environ.get('GITHUB_RUN_ATTEMPT')=='1','automatic or manual retries are not allowed in this entry'
    assert os.environ.get('GITHUB_REPOSITORY_VISIBILITY')=='public'
    rid=os.environ['GITHUB_RUN_ID'];assert rid.isdecimal()
    mem=dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())
    available=int(mem['MemAvailable'].split()[0])*1024
    assert available>=12*GIB,'need at least 12 GiB currently available for this candidate plan'
    assert shutil.disk_usage(root).free>=11*GIB,'need at least 11 GiB free disk to start; requirement is a proposed stop gate, not a measured minimum'
    context=root/'build-source';context.mkdir(exist_ok=False)
    with tarfile.open(root/'source-context.tar.xz','r:xz') as z:z.extractall(context,filter='data')
    build_temp=Path(os.environ['RUNNER_TEMP'])/('aca-build-'+rid)
    build_temp.mkdir(exist_ok=False)
    docker_config=build_temp/'docker-config';docker_config.mkdir()
    # Empty credential configuration; preserve the installed CLI plugin directory explicitly.
    candidate_plugins=[Path('/usr/libexec/docker/cli-plugins'),Path('/usr/lib/docker/cli-plugins'),Path('/usr/local/lib/docker/cli-plugins')]
    plugins=[str(p) for p in candidate_plugins if (p/'docker-buildx').is_file()]
    assert plugins,'preinstalled buildx plugin not found'
    (docker_config/'config.json').write_text(json.dumps({'cliPluginsExtraDirs':plugins}))
    os.environ['DOCKER_CONFIG']=str(docker_config)
    os.environ['BUILDX_CONFIG']=str(build_temp/'buildx-config')
    command(['docker','buildx','version'])
    config=build_temp/'buildkitd.toml'
    config.write_text('[worker.oci]\n  max-parallelism = 1\n')
    builder='aca-cloud-'+rid;image='aca-finish-reason:gh-'+rid
    command(['docker','buildx','create','--name',builder,'--driver','docker-container',
             '--driver-opt','image='+BUILDKIT,'--driver-opt','memory=10g',
             '--driver-opt','memory-swap=10g','--driver-opt','cpu-period=100000',
             '--driver-opt','cpu-quota=300000','--buildkitd-config',str(config)])
    args=['docker','buildx','build','--builder',builder,'--platform','linux/amd64',
          '--progress','plain','--provenance=false','--load','--tag',image,
          '--build-context','node:24.20.0-alpine='+NODE,
          '--build-arg','COMMIT_SHA='+COMMIT,'--file',str(context/'web/Dockerfile'),str(context)]
    started=time.monotonic();reason=None
    try:
        process=subprocess.Popen(args)
        while process.poll() is None:
            if time.monotonic()-started>3600:reason='3600 second build time limit'
            elif shutil.disk_usage(root).free<2*GIB:reason='free disk below 2 GiB'
            if reason:
                process.terminate()
                try:process.wait(timeout=20)
                except subprocess.TimeoutExpired:process.kill();process.wait()
                raise RuntimeError(reason)
            time.sleep(5)
        assert process.returncode==0,'build command failed: '+str(process.returncode)
        image_id=subprocess.check_output(['docker','image','inspect','--format','{{.Id}}',image],text=True).strip()
        result={'source_commit':COMMIT,'source_sha256':SOURCE_SHA,'run_id':rid,
                'image':image,'image_id':image_id,'full_build_passed':True,
                'project_typecheck_passed':False,'candidate_runtime_verified':False,
                'deployed':False,'real14_acceptance_passed':False,
                'builder_memory_limit_gib':10,'available_memory_start_bytes':available}
        (root/'build-result.json').write_text(json.dumps(result,indent=2)+'\n')
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as f:
            f.write('## Candidate build result\n```json\n'+json.dumps(result,indent=2)+'\n```\n')
    finally:
        subprocess.run(['docker','buildx','rm','--force',builder],check=False)

parser=argparse.ArgumentParser()
parser.add_argument('--execute',action='store_true')
parser.add_argument('--check',action='store_true')
opts=parser.parse_args()
root=Path(__file__).resolve().parent.parent
print(json.dumps(source_check(root/'source-context.tar.xz')))
if opts.execute:execute(root)
