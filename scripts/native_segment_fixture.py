#!/usr/bin/env python3
"""Exercise native phase boundaries and real Make argv without a solver or network."""
import json
import os
import re
import shlex
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1]
OWNERS = {
    "admission": "k8s.io/kubernetes/pkg/kubelet/cm/admission",
    "plugin": "k8s.io/kubernetes/pkg/kubelet/cm/devicemanager/plugin/v1beta1",
    "device-manager": "k8s.io/kubernetes/pkg/kubelet/cm/devicemanager",
    "allocation": "k8s.io/kubernetes/pkg/kubelet/allocation",
    "kubelet": "k8s.io/kubernetes/pkg/kubelet",
    "cronjob": "k8s.io/kubernetes/pkg/controller/cronjob",
    "images": "k8s.io/kubernetes/pkg/kubelet/images",
    "container-manager": "k8s.io/kubernetes/pkg/kubelet/cm",
    "node-status": "k8s.io/kubernetes/pkg/kubelet/nodestatus",
    "kube-runtime": "k8s.io/kubernetes/pkg/kubelet/kuberuntime",
}


class NativeSegmentFixture(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "scripts").mkdir()
        for name in ["Makefile", "scripts/build", "scripts/download", "scripts/package-cli",
                     "scripts/version.sh", "scripts/platform.sh", "scripts/git_version.sh"]:
            shutil.copy2(SOURCE / name, self.root / name)
        self.tools = self.root / "providers"
        self.tools.mkdir()
        self.log = self.root / "events.jsonl"
        self.env = dict(os.environ, PATH=str(self.tools)+os.pathsep+os.environ["PATH"],
                        TAG="v1.36.5+k3s1.fleet1", GITHUB_SHA="a"*40, DEBUG="", GOCOVER="",
                        GOOS="linux", GOARCH="amd64", OS="linux", ARCH="amd64", TARGETOS="linux", TARGETARCH="amd64", K3S_BUILD_PACKAGE="",
                        TEST_SEGMENT_LOG=str(self.log), TEST_SEGMENT_GO_ROOT=str(self.root), KUBERNETES_RUN_ID="")
        self.provider("docker", "import json,os,sys\nwith open(os.environ['TEST_SEGMENT_LOG'],'a') as f: f.write(json.dumps(sys.argv[1:])+'\\n')\n")
        self.provider("go", """import json,os,pathlib,subprocess,sys
a=sys.argv[1:]
observe=os.environ.get('TEST_CACHE_OBSERVATION_ONLY')=='yes'
test_graph=os.environ.get('KUBERNETES_TEST_GRAPH','false')=='true'
fields='ImportPath,Stale,StaleReason,Imports,Deps,EmbedFiles'+(',ForTest,TestGoFiles,XTestGoFiles,TestEmbedFiles,XTestEmbedFiles' if test_graph else '')
if observe:
 if not a or a[0] not in ['env','version','list']:raise SystemExit(64)
 if a[0]=='list' and a!=['list','-mod=readonly','-race','-p','2','-export=false','-compiled=false','-test='+('true' if test_graph else 'false'),'-cover=false','-deps','-json='+fields,'net/http']:raise SystemExit(64)
# Model Go-owned cache initialization/touch, without package artifacts.
if observe:
 metadata=pathlib.Path(os.environ['TEST_CACHE_METADATA_DIR'])
 (metadata/'00').mkdir(parents=True,exist_ok=True)
 readme=metadata/'README'
 if not readme.exists():readme.write_text('normal Go cache metadata')
 os.utime(readme,None)
with open(os.environ['TEST_SEGMENT_LOG'],'a') as f:f.write(json.dumps(['go',*a])+'\\n')
if a[:4]==['list','-mod=readonly','-m','-json'] and os.environ.get('TEST_SEGMENT_MODULE_IDENTITIES_FAIL')=='yes':raise SystemExit(47)
if a==['version']:print('go version go1.26.8 linux/amd64')
elif a[:1]==['env']:
 if '-json' in a:print(json.dumps(dict(GOVERSION='go1.26.8',GOMOD=os.environ.get('K3S_SOURCE','/fixture/k3s/').rstrip('/')+'/go.mod',GOOS='linux',GOARCH='amd64',CGO_ENABLED='1',GOCACHE='/different/cache' if os.environ.get('TEST_CACHE_WRONG_PATH')=='yes' else '/root/.cache/go-build',GOMODCACHE='/go/pkg/mod',GOCACHEPROG=os.environ.get('TEST_CACHE_PROG',''),GOFLAGS='')))
 else:print('1' if a[-1]=='CGO_ENABLED' else 'linux' if a[-1] in ['GOOS','GOHOSTOS'] else 'amd64')
elif a[:1]==['list']:
 if '-json='+fields in a:
  rows=[dict(ImportPath='encoding/json'),dict(ImportPath='runtime/race',Stale=True,StaleReason='not installed but available in build cache'),dict(ImportPath='crypto/tls',Stale=True,StaleReason='build ID mismatch',EmbedFiles=['fixture-embedded.bin']),dict(ImportPath='net/http',Stale=True,StaleReason='stale dependency: crypto/tls',Imports=['crypto/tls'],Deps=['crypto/tls','encoding/json','runtime/race'])]
  if test_graph:
   rows[-1].update(TestGoFiles=['http_test.go'],XTestGoFiles=['external_test.go'],TestEmbedFiles=['test-input.bin'],XTestEmbedFiles=['external-input.bin'])
   rows.extend([dict(ImportPath='net/http [net/http.test]',ForTest='net/http'),dict(ImportPath='net/http_test [net/http.test]',ForTest='net/http'),dict(ImportPath='net/http.test')])
  for row in rows:print(json.dumps(row))
 elif '-deps' in a:
  print(json.dumps(dict(ImportPath='encoding/json',Name='json')));print(json.dumps(dict(ImportPath='github.com/k3s-io/k3s/cmd/server',Name='main',Imports=['encoding/json'])))
 elif '{{.Dir}}' in a:
  assert a==['list','-mod=readonly','-f','{{.Dir}}',os.environ['KUBERNETES_TEST_PACKAGE']]
  assert pathlib.Path.cwd().samefile(pathlib.Path(os.environ['TEST_SEGMENT_GO_ROOT']))
  print('' if os.environ.get('TEST_SEGMENT_DIR_EMPTY')=='yes' else os.environ.get('TEST_SEGMENT_GO_DIR',os.environ['TEST_SEGMENT_PACKAGE_DIR']))
 elif '.Replace.Path' in ' '.join(a): print('github.com/containerd/containerd/v2')
 else: print('v1.36.5-k3s1.fleet2' if a[-1]=='k8s.io/kubernetes' else 'v1.0.0')
elif a[:2]==['tool','test2json']:
 sys.exit(subprocess.run(a[a.index('-t')+1:]).returncode)
elif a[:2]==['mod','download']:
 assert a[:3]==['mod','download','-json'] and len(a)==4
 failure=os.environ.get('TEST_MODULE_FAILURE','')
 print(json.dumps(dict(Path='github.com/joshmouch/kubernetes' if a[-1]=='k8s.io/kubernetes' else a[-1],Version='v1.36.5-k3s1.fleet2',Dir='/fixture/module-source',Sum='h1:fixture',GoModSum='h1:fixturemod',Error='fixture module error' if failure else '')))
 sys.exit(1 if failure=='command' else 0)
elif a[:1]==['test']:
 assert a[:7]==['test','-mod=readonly','-race','-p','2','-c','-o'] and len(a)==9 and a[-1]==os.environ['KUBERNETES_TEST_PACKAGE']
 if os.environ.get('TEST_SEGMENT_COMPILE_FAIL')=='yes':raise SystemExit(47)
 output=os.environ.get('TEST_SEGMENT_COMPILE_OUTPUT','normal')
 if output=='missing':raise SystemExit(0)
 p=pathlib.Path(a[a.index('-o')+1]);p.parent.mkdir(parents=True,exist_ok=True)
 p.write_bytes(b'' if output=='empty' else pathlib.Path(os.environ['TEST_SEGMENT_COMPILE_TEMPLATE']).read_bytes());p.chmod(0o644 if output=='not-executable' else 0o755)
elif a[:1]==['build']:
 p=pathlib.Path(a[a.index('-o')+1])
 if str(p)!=os.devnull:p.parent.mkdir(parents=True,exist_ok=True);p.write_text('native compiled output');p.chmod(0o755)
""")
        self.provider("curl", "import pathlib,sys\na=sys.argv[1:];pathlib.Path(a[a.index('-o')+1]).write_text('chart bytes')\n")
        self.provider("yq", "print('https://fixture/chart-1.0.0.tgz')\n")
        upload = self.root / "scripts/build-upload"
        upload.write_text("#!/bin/bash\nexit 0\n")
        upload.chmod(0o755)

    def provider(self, name, body):
        p = self.tools / name
        p.write_text("#!/usr/bin/env python3\n"+body)
        p.chmod(0o755)

    def run_command(self, *argv):
        return subprocess.run(argv, cwd=self.root, env=self.env,
                              text=True, capture_output=True)

    def events(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def docker_run_body(self, stage_name, output, dockerfile="Dockerfile.test"):
        source=(SOURCE/dockerfile).read_text()
        match=re.search(r'^FROM[^\n]+ AS '+re.escape(stage_name)+r'\n',source,re.M)
        stage=source[match.end():].split('\nFROM ',1)[0]
        run=re.search(r'^RUN[ \t]+',stage,re.M)
        self.assertIsNotNone(run,'RUN instruction missing: '+stage_name)
        body=stage[run.end():].replace('\\\n',' ')
        directives=re.match(r'^(?:(?:--mount|--network)=\S+\s+)+',body)
        flags=directives.group().split() if directives else []
        body=body[directives.end():] if directives else body
        # Both exact /out and /out/file are fixture-owned, including space paths.
        body=re.sub(r'/out(?=/|\s|$)',lambda _:shlex.quote(str(output)),body)
        return body,flags

    def docker_copy_output(self, stage_name, output, destination):
        # Project the actual literal COPY sources into an owned disposable export.
        source=(SOURCE/'Dockerfile.test').read_text()
        match=re.search(r'^FROM[^\n]+ AS '+re.escape(stage_name)+r'\n',source,re.M)
        stage=source[match.end():].split('\nFROM ',1)[0]
        command=shlex.split(next(line for line in stage.splitlines() if line.startswith('COPY ')))
        self.assertEqual(command[0],'COPY');self.assertTrue(command[1].startswith('--from='))
        self.assertEqual(command[-1],'/')
        destination.mkdir()
        for name in command[2:-1]:
            self.assertTrue(name.startswith('/out/'))
            item=output/name.removeprefix('/out/')
            if item.is_dir():shutil.copytree(item,destination,dirs_exist_ok=True)
            else:shutil.copy2(item,destination/item.name)
        return command[1].removeprefix('--from=')

    def prepare_server_inputs(self):
        for directory in ["bin", "manifests", "build/static", "pkg/deploy/embed", "pkg/static/embed"]:
            (self.root / directory).mkdir(parents=True, exist_ok=True)
        (self.root / "manifests/chart.yaml").write_text("chart source")
        (self.root / "build/static/rootfs").write_text("root source")
