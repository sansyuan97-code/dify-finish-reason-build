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
    assert os.environ.get('GITHUB_EVENT_NAME')=='push'
    assert os.environ.get('GITHUB_REF_NAME')=='step5-source-reader-20261030'
    assert os.environ.get('GITHUB_RUN_ATTEMPT')=='1','automatic or manual retries are not allowed in this entry'
    assert os.environ.get('GITHUB_REPOSITORY_VISIBILITY')=='public'
    rid=os.environ['GITHUB_RUN_ID'];assert rid.isdecimal()
    mem=dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())
    available=int(mem['MemAvailable'].split()[0])*1024
    assert available>=13*GIB,'need at least 13 GiB currently available for this candidate plan'
    assert shutil.disk_usage(root).free>=11*GIB,'need at least 11 GiB free disk to start; requirement is a proposed stop gate, not a measured minimum'
    context=root/'build-source';context.mkdir(exist_ok=False)
    with tarfile.open(root/'source-context.tar.xz','r:xz') as z:z.extractall(context,filter='data')
    cli_manifest='{\n  "name": "@langgenius/difyctl",\n  "version": "1.17.1",\n  "description": "Dify command-line interface",\n  "license": "Apache-2.0",\n  "files": [\n    "README.md",\n    "bin",\n    "dist"\n  ],\n  "type": "module",\n  "exports": {\n    ".": {\n      "types": "./dist/index.d.ts",\n      "import": "./dist/index.js"\n    }\n  },\n  "scripts": {\n    "build": "vp pack",\n    "dev": "bun bin/dev.js",\n    "test": "vp test",\n    "test:coverage": "vp test --coverage",\n    "test:e2e": "vp test --config vitest.e2e.config.ts",\n    "test:e2e:smoke": "vp test --config vitest.e2e.config.ts --testNamePattern \\"\\\\[P0\\\\]\\"",\n    "test:e2e:local": "DIFY_E2E_MODE=local vp test --config vitest.e2e.config.ts",\n    "type-check": "tsc",\n    "tree:gen": "bun scripts/generate-command-tree.ts",\n    "tree:check": "bun scripts/generate-command-tree.ts --check",\n    "prebuild": "pnpm tree:gen",\n    "predev": "pnpm tree:gen",\n    "pretest": "pnpm tree:gen",\n    "ci": "pnpm tree:check && pnpm test:coverage && pnpm build",\n    "clean": "rm -rf dist node_modules/.cache",\n    "version:info": "bun scripts/print-buildinfo.ts",\n    "build:bin": "scripts/release-build.sh",\n    "build:bin:local": "DIFYCTL_CHANNEL=dev scripts/release-build.sh"\n  },\n  "dependencies": {\n    "@dify/contracts": "workspace:*",\n    "@napi-rs/keyring": "catalog:",\n    "@orpc/client": "catalog:",\n    "@orpc/contract": "catalog:",\n    "@orpc/openapi-client": "catalog:",\n    "cli-table3": "catalog:",\n    "eventsource-parser": "catalog:",\n    "js-yaml": "catalog:",\n    "lockfile": "catalog:",\n    "open": "catalog:",\n    "ora": "catalog:",\n    "picocolors": "catalog:",\n    "std-semver": "catalog:",\n    "undici": "catalog:",\n    "zod": "catalog:"\n  },\n  "devDependencies": {\n    "@dify/tsconfig": "workspace:*",\n    "@hono/node-server": "catalog:",\n    "@types/lockfile": "catalog:",\n    "@types/node": "catalog:",\n    "@typescript/native": "catalog:",\n    "@vitest/coverage-v8": "catalog:",\n    "hono": "catalog:",\n    "typescript": "catalog:",\n    "vite": "catalog:",\n    "vite-plus": "catalog:",\n    "vitest": "catalog:"\n  },\n  "engines": {\n    "node": "^24.20.0"\n  },\n  "difyctl": {\n    "channel": "stable",\n    "compat": {\n      "minDify": "1.16.0",\n      "maxDify": "1.17.1"\n    },\n    "release": {\n      "tagPrefix": "difyctl-v",\n      "binName": "difyctl",\n      "checksumsSuffix": "-checksums.txt",\n      "targets": [\n        {\n          "id": "linux-x64",\n          "bunTarget": "bun-linux-x64",\n          "exe": false\n        },\n        {\n          "id": "linux-arm64",\n          "bunTarget": "bun-linux-arm64",\n          "exe": false\n        },\n        {\n          "id": "darwin-x64",\n          "bunTarget": "bun-darwin-x64",\n          "exe": false\n        },\n        {\n          "id": "darwin-arm64",\n          "bunTarget": "bun-darwin-arm64",\n          "exe": false\n        },\n        {\n          "id": "windows-x64",\n          "bunTarget": "bun-windows-x64",\n          "exe": true\n        }\n      ]\n    }\n  }\n}\n'
    assert hashlib.sha256(cli_manifest.encode()).hexdigest()=='557f65b874173874977d887265bc1654f57c944a3eaab102db21af511ece5247'
    (context/'cli').mkdir()
    (context/'cli/package.json').write_text(cli_manifest)
    patch=root/'source-reader.patch'
    assert hashlib.sha256(patch.read_bytes()).hexdigest()=='78fbe80d2f64ac24fc4b1e0838efc2079d228ed8f4d14f0bc855b4397ef2d2a8'
    command(['git','apply','--check',str(patch)],cwd=context)
    command(['git','apply',str(patch)],cwd=context)
    # Formatting and package-owned checks run before producing a candidate image.
    # The upstream production-only context omits root checker configuration and
    # shared package sources. Include the fixed public archive's test/check inputs.
    ignore=context/'web/Dockerfile.dockerignore'
    ignore_text=ignore.read_text()
    include='!vite.config.ts\n!lint.config.ts\n!eslint.config.mjs\n!oxlint-suppressions.json\n!.editorconfig\n!.gitignore\n!LICENSE\n!scripts/\n!scripts/**\n!packages/**\n!cli/\n!cli/package.json\n'
    assert '\n.git\n' in ignore_text
    ignore.write_text(ignore_text.replace('\n.git\n','\n'+include+'\n.git\n'))
    dockerfile=context/'web/Dockerfile'
    source=dockerfile.read_text()
    needle='RUN pnpm build && pnpm build:vinext'
    assert needle in source
    files='web/app/components/workflow/run/output-panel.tsx web/app/components/workflow/run/result-panel.tsx web/app/components/workflow/run/__tests__/output-panel.spec.tsx web/app/components/workflow/run/__tests__/result-panel.spec.tsx'
    checks='RUN cd /app && node --input-type=module -e '+'\'import { resolveConfig } from \'"\'"\'vite-plus\'"\'"\'; import fs from \'"\'"\'node:fs\'"\'"\'; const c=await resolveConfig({configFile:\'"\'"\'/app/vite.config.ts\'"\'"\'},\'"\'"\'build\'"\'"\'); console.log(JSON.stringify({cwd:process.cwd(),configFile:c.configFile,fmt:!!c.fmt,lint:!!c.lint,types:c.lint?.options,workspace:fs.existsSync(\'"\'"\'/app/pnpm-workspace.yaml\'"\'"\')})); if(!c.fmt||!c.lint) process.exit(1)\''+'\nRUN cd /app && pnpm exec vp fmt '+files+'\nRUN pnpm exec vp test run --project unit app/components/workflow/run/__tests__/output-panel.spec.tsx app/components/workflow/run/__tests__/result-panel.spec.tsx\nRUN cd /app/packages/dev-proxy && pnpm run build\nRUN cd /app && pnpm exec vp run -w check\n'
    dockerfile.write_text(source.replace(needle,checks+needle))
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
             '--driver-opt','image='+BUILDKIT,'--driver-opt','memory=12g',
             '--driver-opt','memory-swap=12g','--driver-opt','cpu-period=100000',
             '--driver-opt','cpu-quota=200000','--buildkitd-config',str(config)])
    args=['docker','buildx','build','--builder',builder,'--platform','linux/amd64',
          '--progress','plain','--provenance=false','--load','--tag',image,
          '--build-context','node:24.20.0-alpine='+NODE,
          '--build-arg','COMMIT_SHA='+COMMIT,'--file',str(context/'web/Dockerfile'),str(context)]
    print(json.dumps({'resource_plan': {'builder_memory_gib':12,'builder_cpu_limit':2,
          'swap_in_builder':False,'min_available_memory_gib':13,'build_seconds_limit':3600},
          'available_memory_start_bytes':available,'free_disk_start_bytes':shutil.disk_usage(root).free}),flush=True)
    def memory_sample(stage):
        sample={'resource_sample':stage,'elapsed_seconds':round(time.monotonic()-started,1)}
        try:
            ids=subprocess.check_output(['docker','ps','-aq','--filter',
                'name=^/buildx_buildkit_'+builder+'0$'],text=True,timeout=5).split()
            if len(ids)!=1:
                sample['available']=False
            else:
                command_text='for f in memory.current memory.peak memory.max memory.events; do if [ -r /sys/fs/cgroup/$f ]; then echo "$f"; cat /sys/fs/cgroup/$f; fi; done'
                probe=subprocess.run(['docker','exec',ids[0],'sh','-c',command_text],text=True,capture_output=True,timeout=5)
                sample.update(cgroup_probe_exit=probe.returncode,cgroup_memory=probe.stdout[:4096])
                state=subprocess.run(['docker','inspect','--format','{{json .State}}',ids[0]],text=True,capture_output=True,timeout=5)
                sample['container_state']=state.stdout[:4096]
        except (OSError,subprocess.SubprocessError) as error:
            sample.update(available=False,error_type=type(error).__name__)
        print(json.dumps(sample),flush=True)
    started=time.monotonic();reason=None;next_sample=started
    try:
        process=subprocess.Popen(args)
        while process.poll() is None:
            if time.monotonic()>=next_sample:
                memory_sample('running');next_sample=time.monotonic()+30
            if time.monotonic()-started>3600:reason='3600 second build time limit'
            elif shutil.disk_usage(root).free<2*GIB:reason='free disk below 2 GiB'
            if reason:
                process.terminate()
                try:process.wait(timeout=20)
                except subprocess.TimeoutExpired:process.kill();process.wait()
                raise RuntimeError(reason)
            time.sleep(5)
        memory_sample('after_build_process')
        assert process.returncode==0,'build command failed: '+str(process.returncode)
        image_id=subprocess.check_output(['docker','image','inspect','--format','{{.Id}}',image],text=True).strip()
        result={'source_commit':COMMIT,'source_sha256':SOURCE_SHA,'run_id':rid,
                'image':image,'image_id':image_id,'full_build_passed':True,
                'project_typecheck_passed':True,'candidate_runtime_verified':False,
                'deployed':False,'real14_acceptance_passed':False,
                'builder_memory_limit_gib':12,'available_memory_start_bytes':available}
        (root/'build-result.json').write_text(json.dumps(result,indent=2)+'\n')
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as f:
            f.write('## Candidate build result\n```json\n'+json.dumps(result,indent=2)+'\n```\n')
    finally:
        memory_sample('before_builder_cleanup')
        subprocess.run(['docker','buildx','rm','--force',builder],check=False)

parser=argparse.ArgumentParser()
parser.add_argument('--execute',action='store_true')
parser.add_argument('--check',action='store_true')
opts=parser.parse_args()
root=Path(__file__).resolve().parent.parent
print(json.dumps(source_check(root/'source-context.tar.xz')))
if opts.execute:execute(root)
