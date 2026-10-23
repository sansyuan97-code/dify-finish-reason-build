"""B04 image-only smoke check. --check is offline and never invokes Docker."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

REPO = 'sansyuan97-code/dify-finish-reason-build'
IMAGE = 'ghcr.io/sansyuan97-code/dify-finish-reason-candidate@sha256:3ebe4e18ef2894409ecb1b3b82523c463dc7a47afa2aba50e7d22b489eb483f7'
CONFIG_ID = 'sha256:7ef22d325bc9a03ba48a9a58603be3ffb75e5db13eb42bf6f5d8d519e55afd87'
ENTRY_SHA = '71381d7cb411bc7df99ebe08d8e6f4b7c1995e280d96bc6940583bf8c6c4e9fd'
APPROVAL = 'VERIFY-B04-ONCE'
GIB = 1024 ** 3
PROBE = r'''
const http = require('node:http');
const fs = require('node:fs');
const crypto = require('node:crypto');
const os = require('node:os');
const origin = 'http://127.0.0.1:3000';
function fail(message) { throw new Error(message); }
function get(path, depth = 0) {
  const url = new URL(path, origin);
  if (url.origin !== origin || depth > 3) fail('non-local or excessive redirect');
  return new Promise((resolve, reject) => {
    const req = http.get(url, {headers: {'Accept': '*/*'}}, res => {
      const chunks = []; let count = 0;
      res.on('error', reject);
      res.on('data', b => {
        count += b.length;
        if (count > 4 * 1024 * 1024) res.destroy(new Error('response too large'));
        else chunks.push(b);
      });
      res.on('end', () => resolve({status: res.statusCode, headers: res.headers, body: Buffer.concat(chunks)}));
    });
    req.setTimeout(10000, () => req.destroy(new Error('request timeout')));
    req.on('error', reject);
  }).then(r => {
    if ([301, 302, 303, 307, 308].includes(r.status)) {
      if (!r.headers.location) fail('redirect without location');
      return get(new URL(r.headers.location, url).href, depth + 1);
    }
    return r;
  });
}
(async () => {
  const deadline = Date.now() + 120000;
  let page;
  // Readiness waiting only: never restart the container or repeat a failed HTTP check.
  while (true) {
    try { page = await get('/signin'); break; }
    catch (e) {
      if (!['ECONNREFUSED', 'ECONNRESET'].includes(e.code) || Date.now() >= deadline) throw e;
      await new Promise(resolve => setTimeout(resolve, 2000));
    }
  }
  const html = page.body.toString('utf8');
  if (page.status !== 200 || !String(page.headers['content-type']).includes('text/html') || !/<html[\s>]/i.test(html))
    fail('signin did not return an HTML page with HTTP 200');
  const scripts = [...html.matchAll(/<script\b[^>]*\bsrc=["']([^"']+)["']/gi)].map(m => m[1].replace(/&amp;/g, '&'));
  const asset = scripts.find(s => s.startsWith('/') && !s.startsWith('//') && /\.m?js(?:[?#]|$)/.test(s));
  if (!asset) fail('no same-origin JavaScript asset in signin HTML');
  const js = await get(asset);
  if (js.status !== 200 || !/(javascript|ecmascript)/i.test(String(js.headers['content-type'])) || js.body.length < 100)
    fail('referenced JavaScript asset did not load');
  const net = os.networkInterfaces();
  if (Object.entries(net).some(([name, addresses]) => name !== 'lo' || addresses.some(a => !a.internal)))
    fail('unexpected non-loopback interface');
  console.log(JSON.stringify({
    signin_status: page.status, signin_bytes: page.body.length,
    script_path: asset, script_status: js.status, script_bytes: js.body.length,
    entrypoint_sha256: crypto.createHash('sha256').update(fs.readFileSync('/app/entrypoint.sh')).digest('hex'),
    pid1: fs.readFileSync('/proc/1/cmdline', 'utf8').replace(/\0/g, ' ').trim(),
    pid1_executable: fs.readlinkSync('/proc/1/exe'), probe_executable: process.execPath,
    uid: process.getuid(), interfaces: Object.keys(net),
    browser_rendering_verified: false, editor_integration_verified: false
  }));
})().catch(e => { console.error(e.message); process.exitCode = 1; });
'''


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def run(args, timeout=30, **kwargs):
    return subprocess.run(args, check=True, text=True, capture_output=True, timeout=timeout, **kwargs).stdout.strip()


def verified(result, errors):
    return (not errors and result['cloud_pull_verified'] and len(result['targets']) == 2
            and all(t['passed'] for t in result['targets'].values())
            and len(result['cleanup']) == 2 and all(result['cleanup'].values())
            and result.get('credentials_removed') is True)


def execution_gate():
    require(sys.platform == 'linux', 'cloud Linux runner only')
    expected = {'GITHUB_ACTIONS': 'true', 'GITHUB_REPOSITORY': REPO,
                'GITHUB_EVENT_NAME': 'workflow_dispatch', 'GITHUB_RUN_ATTEMPT': '1',
                'ACA_RUNTIME_APPROVAL': APPROVAL}
    for key, value in expected.items():
        require(os.environ.get(key) == value, 'execution gate failed: ' + key)
    rid = os.environ.get('GITHUB_RUN_ID', '')
    require(rid.isdecimal(), 'invalid run ID')
    return rid


def inspect_image():
    fmt = '{"id":{{json .Id}},"os":{{json .Os}},"arch":{{json .Architecture}},"digests":{{json .RepoDigests}},"user":{{json .Config.User}}}'
    image = json.loads(run(['docker', 'image', 'inspect', '--format', fmt, IMAGE]))
    require(image['id'] == CONFIG_ID, 'unexpected image config ID')
    require(image['os'] == 'linux' and image['arch'] == 'amd64', 'unexpected image platform')
    require(IMAGE in image['digests'], 'immutable registry digest absent')
    require(image['user'] == 'dify', 'unexpected runtime user')
    return image


def state(name):
    fmt = '{"state":{{json .State}},"image":{{json .Image}},"network":{{json .HostConfig.NetworkMode}},"ports":{{json .HostConfig.PortBindings}},"mounts":{{json .Mounts}},"memory":{{json .HostConfig.Memory}},"swap":{{json .HostConfig.MemorySwap}},"cpu":{{json .HostConfig.NanoCpus}},"restart":{{json .HostConfig.RestartPolicy.Name}}}'
    return json.loads(run(['docker', 'container', 'inspect', '--format', fmt, name]))


def validate_container(data):
    require(data['image'] == CONFIG_ID and data['network'] == 'none', 'unexpected image/network')
    require(not data['ports'] and not data['mounts'], 'unexpected ports/mounts')
    require(data['memory'] == 2 * GIB and data['swap'] == 2 * GIB and data['cpu'] == 2000000000, 'resource limit mismatch')
    require(data['restart'] == 'no', 'unexpected restart policy')
    require(data['state']['Running'] and not data['state']['OOMKilled'] and data['state']['Restarting'] is False, 'runtime exited or restarted')


def validate_probe(target, probe):
    # Next�ٷ���ڻ��д���̱��⣬����Ҫ��/proc/1/cmdline����server.js������
    require(probe['entrypoint_sha256'] == ENTRY_SHA, 'official entrypoint hash mismatch')
    require(probe['uid'] == 1001, 'unexpected runtime UID')
    require(probe['pid1_executable'] == probe['probe_executable'], 'PID 1 is not the image Node executable')
    expected = {'next': 'next-server (v16.3.4)', 'vinext': 'node /app/targets/vinext/server.js'}
    require(target in expected and probe['pid1'] == expected[target], 'unexpected target process identity')


def execute():
    rid = execution_gate()  # Must fail before Docker or credential handling on a local machine.
    names = ['aca-runtime-' + rid + '-' + target for target in ('next', 'vinext')]
    temp_root = Path(os.environ['RUNNER_TEMP']).resolve()
    cfg = temp_root / ('aca-runtime-auth-' + rid)
    require(cfg.parent == temp_root and not cfg.exists(), 'credential directory collision')
    cfg.mkdir(mode=0o700)
    os.environ['DOCKER_CONFIG'] = str(cfg)
    result = {'image': IMAGE, 'config_id': CONFIG_ID, 'run_id': rid, 'run_attempt': 1,
              'targets': {}, 'cleanup': {}, 'cloud_pull_verified': False,
              'candidate_runtime_verified': False, 'new_builds': 0,
              'local_retrieval_verified': False, 'rollback_rehearsal_passed': False,
              'deployed': False, 'real14_acceptance_passed': False}
    errors = []
    try:
        mem = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
        result['available_memory_start_bytes'] = int(mem['MemAvailable'].split()[0]) * 1024
        require(result['available_memory_start_bytes'] >= 3 * GIB, 'need 3 GiB currently available for this proposed runtime check')
        require(shutil.disk_usage(temp_root).free >= 10 * GIB, 'need 10 GiB free disk for this proposed runtime check')
        token = os.environ.pop('GHCR_TOKEN', '')
        require(bool(token), 'ephemeral registry token unavailable')
        try:
            run(['docker', 'login', 'ghcr.io', '--username', 'sansyuan97-code', '--password-stdin'], input=token, timeout=45)
        finally:
            token = None
        run(['docker', 'pull', '--platform', 'linux/amd64', IMAGE], timeout=480)
        result['image_metadata'] = inspect_image()
        result['cloud_pull_verified'] = True
        # Erase registry credentials before starting any application container.
        run(['docker', 'logout', 'ghcr.io'])
        for target, name in zip(('next', 'vinext'), names):
            info = {'passed': False}
            result['targets'][target] = info
            try:
                run(['docker', 'run', '--detach', '--pull', 'never', '--name', name,
                     '--network', 'none', '--restart', 'no', '--memory', '2g', '--memory-swap', '2g',
                     '--cpus', '2', '--pids-limit', '256', '--cap-drop', 'ALL',
                     '--security-opt', 'no-new-privileges', '--log-opt', 'max-size=2m', '--log-opt', 'max-file=1',
                     '--env', 'HOSTNAME=127.0.0.1', '--env', 'PORT=3000', '--env', 'NEXT_TELEMETRY_DISABLED=1',
                     '--env', 'CONSOLE_API_URL=http://127.0.0.1:5001', '--env', 'APP_API_URL=http://127.0.0.1:5001',
                     '--env', 'MARKETPLACE_API_URL=http://127.0.0.1:5001', '--env', 'MARKETPLACE_URL=http://127.0.0.1:5001',
                     '--env', 'EXPERIMENTAL_ENABLE_VINEXT=' + ('true' if target == 'vinext' else 'false'), IMAGE])
                validate_container(state(name))
                probe = json.loads(run(['docker', 'exec', name, 'node', '-e', PROBE], timeout=150))
                info['probe'] = probe  # �ȱ���ԭʼ�ض������ݼ��ʧ��Ҳ���ܶ�ʧ֤�ݡ�
                validate_probe(target, probe)
                info['final_state'] = state(name)
                validate_container(info['final_state'])
                info['passed'] = True
            except Exception as exc:
                info['failure_type'] = type(exc).__name__
                errors.append(target + ': ' + type(exc).__name__)
                if isinstance(exc, subprocess.CalledProcessError):
                    info['check_error'] = (exc.stderr or '')[-2000:]
                elif isinstance(exc, RuntimeError):
                    info['check_error'] = str(exc)
            finally:
                if run(['docker', 'ps', '-a', '--filter', 'name=^/' + name + '$', '--format', '{{.Names}}']):
                    log = subprocess.run(['docker', 'logs', '--tail', '80', name], check=True,
                                         text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
                    info['logs_tail'] = log.stdout[-12000:]
                    info['state_at_cleanup'] = state(name)
                    run(['docker', 'rm', '--force', name])
                    require(not run(['docker', 'ps', '-a', '--filter', 'name=^/' + name + '$', '--format', '{{.Names}}']), 'container cleanup failed')
    except Exception as exc:
        errors.append('job: ' + type(exc).__name__)
        # Never stringify login exceptions: the exception may hold password input.
        if isinstance(exc, RuntimeError):
            result['gate_error'] = str(exc)
    finally:
        for name in names:
            try:
                found = run(['docker', 'ps', '-a', '--filter', 'name=^/' + name + '$', '--format', '{{.Names}}'])
                if found:
                    run(['docker', 'rm', '--force', name])
                result['cleanup'][name] = not bool(run(['docker', 'ps', '-a', '--filter', 'name=^/' + name + '$', '--format', '{{.Names}}']))
            except Exception:
                result['cleanup'][name] = False
                errors.append('container cleanup unverified')
        # Fixed, validated directory created by this job; never delete the runner temp root.
        try:
            shutil.rmtree(cfg)
            result['credentials_removed'] = not cfg.exists()
        except Exception:
            result['credentials_removed'] = False
            errors.append('credential cleanup unverified')
        result['errors'] = errors
        result['candidate_runtime_verified'] = verified(result, errors)
        payload = json.dumps(result, indent=2, ensure_ascii=False)
        Path('runtime-result.json').write_text(payload, encoding='utf-8')
        print(payload)
        summary = os.environ.get('GITHUB_STEP_SUMMARY')
        if summary:
            with open(summary, 'a', encoding='utf-8') as stream:
                stream.write('## B04 isolated runtime check\n\n```json\n' + payload + '\n```\n')
    require(result['candidate_runtime_verified'], 'runtime check incomplete or failed; do not retry automatically')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    require(args.check != args.execute, 'choose exactly one mode')
    if args.check:
        print(json.dumps({'offline_plan_check': True, 'image': IMAGE, 'config_id': CONFIG_ID,
                          'probe_sha256': hashlib.sha256(PROBE.encode()).hexdigest(),
                          'docker_calls': 0, 'network_calls': 0,
                          'candidate_runtime_verified': False, 'deployed': False}))
    else:
        execute()


if __name__ == '__main__':
    main()
