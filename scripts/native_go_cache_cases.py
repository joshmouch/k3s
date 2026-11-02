"""Native Go module/cache boundaries, exercised through the existing unittest entry."""
import json
import re
from native_segment_fixture import SOURCE, NativeSegmentFixture

class NativeGoCacheCases(NativeSegmentFixture):
    def test_real_make_cache_address_and_native_binary_stages(self):
        pattern=next(r['match']['commandRegex'] for r in json.loads((SOURCE/'.ai-fleet/tool-execution-policy.json').read_text())['rules'] if r['name']=='k3s-native-construction-segments')
        for identity in ['warm-request-a','warm-request-b']:
            self.log.unlink(missing_ok=True)
            command=['make','kubernetes-cache-packages','KUBERNETES_BUILD_PACKAGE=encoding/json','KUBERNETES_RUN_ID='+identity]
            result=self.run_command(*command);self.assertEqual(result.returncode,0,result.stderr)
            calls=self.events();self.assertEqual(len(calls),1,calls)
            self.assertRegex('/usr/bin/env BUILDX_BUILDER=ai-fleet-cluster /usr/bin/'+' '.join(command),pattern)
            self.assertIn('KUBERNETES_BUILD_PACKAGE=encoding/json',calls[0]);self.assertIn('KUBERNETES_RUN_ID='+identity,calls[0])
            self.assertNotIn('--no-cache-filter',calls[0])
        for target, stage in {
            "binary-infra": "infra", "binary-deps-runc": "download-runc",
            "binary-deps-rootfs": "download-rootfs", "binary-deps-containerd": "download-containerd",
            "binary-deps-charts": "manifests", "binary-cni": "build-cni",
            "binary-server": "build-server", "binary-shim": "build-shim", "binary-runc": "build-runc",
            "binary-package-prepare": "package-prepare", "binary-package-compress": "package-compress",
            "binary-package-cli": "build",
        }.items():
            self.log.unlink(missing_ok=True)
            result = self.run_command("make", target)
            self.assertEqual(result.returncode, 0, result.stderr)
            args = self.events()[0]
            self.assertEqual(args[args.index("--target")+1], stage)
            self.assertEqual(args[args.index("--output")+1], "type=cacheonly")
        for target, assignment, stage in [
            ("binary-cache-packages", "K3S_BUILD_PACKAGE=encoding/json", "binary-package-cache"),
            ("binary-package-graph", None, "binary-package-graph-result"),
            ("binary-export", None, "result"),
        ]:
            for identity in ['warm-request-a','warm-request-b'] if assignment else [None]:
                self.log.unlink(missing_ok=True)
                command=['make',target]+([assignment,'KUBERNETES_RUN_ID='+identity] if assignment else [])
                result=self.run_command(*command);self.assertEqual(result.returncode,0,result.stderr)
                calls=self.events();self.assertEqual(len(calls),1,calls)
                self.assertRegex('/usr/bin/env BUILDX_BUILDER=ai-fleet-cluster /usr/bin/'+' '.join(command),pattern)
                self.assertEqual(calls[0][calls[0].index('--target')+1],stage)
                if assignment:
                    self.assertIn(assignment,calls[0]);self.assertIn('KUBERNETES_RUN_ID='+identity,calls[0]);self.assertNotIn('--no-cache-filter',calls[0])
        for target,variable in [('kubernetes-cache-packages','KUBERNETES_BUILD_PACKAGE'),('binary-cache-packages','K3S_BUILD_PACKAGE')]:
            for identity in ['', '-n']:
                self.log.unlink(missing_ok=True)
                command=['make',target,variable+'=encoding/json','KUBERNETES_RUN_ID='+identity]
                result=self.run_command(*command);self.assertNotEqual(result.returncode,0,result.stdout);self.assertEqual(self.events(),[])
                self.assertIsNone(re.fullmatch(pattern,'/usr/bin/env BUILDX_BUILDER=ai-fleet-cluster /usr/bin/'+' '.join(command)))

    def test_cache_admissions_reject_options_whitespace_multi_address_and_split_goals(self):
        for target, variable in [("kubernetes-cache-packages", "KUBERNETES_BUILD_PACKAGE"),
                                 ("kubernetes-cache-state", "KUBERNETES_BUILD_PACKAGE"),
                                 ("binary-cache-packages", "K3S_BUILD_PACKAGE")]:
            identity=["KUBERNETES_RUN_ID=fixture-address-guard"]
            for value in ["", " ", "-n", "encoding/json fmt", "encoding/json!"]:
                self.log.unlink(missing_ok=True)
                result = self.run_command("make", target, variable+"="+value, *identity)
                self.assertNotEqual(result.returncode, 0, (target,value,result.stdout))
                self.assertEqual(self.events(), [], (target,value))
            self.log.unlink(missing_ok=True)
            result = self.run_command("make", target, variable+"=encoding/json", *identity, "fmt")
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertEqual(self.events(), [])

    def test_cache_state_actual_run_is_observation_only_and_real_make_is_fresh(self):
        pattern=next(r['match']['commandRegex'] for r in json.loads((SOURCE/'.ai-fleet/tool-execution-policy.json').read_text())['rules'] if r['name']=='k3s-native-construction-segments')
        observed=[]
        for identity in ['owned-request-a','owned-request-b']:
            self.log.unlink(missing_ok=True)
            command=['make','kubernetes-cache-state','KUBERNETES_BUILD_PACKAGE=net/http','KUBERNETES_RUN_ID='+identity]
            result=self.run_command(*command)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertRegex('/usr/bin/env BUILDX_BUILDER=ai-fleet-cluster /usr/bin/'+' '.join(command),pattern)
            calls=self.events(); self.assertEqual(len(calls),1,calls)
            argv=calls[0]
            self.assertEqual(argv[argv.index('--target')+1],'kubernetes-cache-state-result')
            self.assertNotIn('--no-cache-filter',argv)
            self.assertNotIn('--no-cache',argv)
            self.assertIn('KUBERNETES_RUN_ID='+identity,argv)
            self.assertIn('KUBERNETES_BUILD_PACKAGE=net/http',argv)
            self.assertEqual(argv[argv.index('--metadata-file')+1],'dist/native-kubernetes-tests/kubernetes-cache-state/buildx-metadata.json')
            self.assertEqual(argv[argv.index('--output')+1],'type=local,dest=dist/native-kubernetes-tests/kubernetes-cache-state')
            observed.append(argv)
        self.assertNotEqual(observed[0],observed[1])
        for identity in [None,'',' ','-n','a/b','a b','bad!']:
            self.log.unlink(missing_ok=True)
            command=['make','kubernetes-cache-state','KUBERNETES_BUILD_PACKAGE=net/http']
            if identity is not None:command.append('KUBERNETES_RUN_ID='+identity)
            result=self.run_command(*command)
            self.assertNotEqual(result.returncode,0,(identity,result.stdout))
            self.assertEqual(self.events(),[])
            self.assertIsNone(re.fullmatch(pattern,'/usr/bin/env BUILDX_BUILDER=ai-fleet-cluster /usr/bin/'+' '.join(command)))
        stage=(SOURCE/'Dockerfile.test').read_text().split('FROM kubernetes-test-base AS kubernetes-cache-state\n',1)[1].split('\nFROM ',1)[0]
        self.assertIn('ARG KUBERNETES_RUN_ID\n',stage)
        output=self.root/'cache observation output'
        body,flags=self.docker_run_body('kubernetes-cache-state',output)
        self.assertEqual(flags,['--network=none','--mount=type=bind,source=.,target=${K3S_SOURCE},readonly','--mount=type=cache,id=gomod,target=/go/pkg/mod,readonly','--mount=type=cache,id=gobuild-${TARGETOS}-${TARGETARCH},target=/root/.cache/go-build'])
        self.provider('cc',"import sys\nassert sys.argv[1:]==['--version']\nprint('fixture compiler identity')\n")
        # The real mount assertion above requires writable normal gobuild metadata;
        # source/gomod remain read-only. The provider models that primitive need.
        metadata=self.root/'normal cache metadata'
        self.assertFalse(metadata.exists())
        self.env.update(TEST_CACHE_OBSERVATION_ONLY='yes',KUBERNETES_BUILD_PACKAGE='net/http',
                        TEST_CACHE_METADATA_DIR=str(metadata),KUBERNETES_RUN_ID='owned-request-a')
        self.log.unlink(missing_ok=True)
        result=self.run_command('bash','-euo','pipefail','-c',body)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertTrue((metadata/'00').is_dir())
        self.assertEqual((metadata/'README').read_text(),'normal Go cache metadata')
        self.assertEqual(sorted(p.name for p in metadata.iterdir()),['00','README'])
        rows=[json.loads(line) for line in (output/'cache-state.json').read_text().splitlines()]
        self.assertEqual(len(rows),4)
        self.assertNotIn('Stale',rows[0])
        self.assertEqual(rows[1]['StaleReason'],'not installed but available in build cache')
        self.assertEqual(rows[2]['StaleReason'],'build ID mismatch')
        self.assertEqual(rows[2]['EmbedFiles'],['fixture-embedded.bin'])
        self.assertEqual(rows[3]['Imports'],['crypto/tls'])
        self.assertEqual(json.loads((output/'cache-state-counts.json').read_text()),dict(records=4,inputRecords=1))
        self.assertEqual((output/'package.txt').read_text(),'net/http\n')
        self.assertEqual((output/'run-id.txt').read_text(),'owned-request-a\n')
        calls=self.events()
        self.assertTrue(all(c[:2] not in [['go','build'],['go','test'],['go','tool']] for c in calls))
        for old,new in [(',EmbedFiles',''),('-export=false','-export=true'),('-compiled=false','-compiled=true'),('-test=false','-test=true'),('-cover=false','-cover=true'),('go list -mod=readonly','go build -mod=readonly'),('go list -mod=readonly','go tool compile -mod=readonly')]:
            self.log.unlink(missing_ok=True)
            result=self.run_command('bash','-euo','pipefail','-c',body.replace(old,new))
            self.assertNotEqual(result.returncode,0,result.stdout)
        for overrides in [dict(TEST_CACHE_WRONG_PATH='yes'),dict(TEST_CACHE_PROG='external-provider')]:
            self.env.update(overrides)
            self.log.unlink(missing_ok=True)
            result=self.run_command('bash','-euo','pipefail','-c',body)
            self.assertNotEqual(result.returncode,0,result.stdout)
            self.assertFalse(any(c[:2]==['go','list'] for c in self.events()))
            for key in overrides:self.env.pop(key)
        self.env['KUBERNETES_RUN_ID']='owned-request-b'
        self.log.unlink(missing_ok=True)
        result=self.run_command('bash','-euo','pipefail','-c',body)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual((output/'run-id.txt').read_text(),'owned-request-b\n')
        for identity in ['', '-n', 'a/b', 'a b']:
            self.env['KUBERNETES_RUN_ID']=identity
            self.log.unlink(missing_ok=True)
            result=self.run_command('bash','-euo','pipefail','-c',body)
            self.assertNotEqual(result.returncode,0,result.stdout)
            self.assertEqual(self.events(),[])

    def test_native_graph_action_entire_stdout_is_only_go_json(self):
        self.prepare_server_inputs()
        result = self.run_command("bash", "scripts/build", "graph")
        self.assertEqual(result.returncode, 0, result.stderr)
        remaining = result.stdout
        rows = []
        decoder = json.JSONDecoder()
        while remaining.strip():
            row,end = decoder.raw_decode(remaining.lstrip())
            rows.append(row)
            remaining = remaining.lstrip()[end:]
        self.assertEqual([r["ImportPath"] for r in rows], ["encoding/json", "github.com/k3s-io/k3s/cmd/server"])
        self.assertEqual([r for r in self.events() if r[:2]==["go","build"]], [])

    def test_native_cache_action_one_address_and_no_generated_binary(self):
        self.assertTrue((SOURCE/'scripts/build').stat().st_mode & 0o111)
        self.assertEqual((self.root/'scripts/build').stat().st_mode & 0o777,(SOURCE/'scripts/build').stat().st_mode & 0o777)
        self.prepare_server_inputs()
        (self.tools/'xx-go').symlink_to(self.tools/'go')
        for dockerfile,stage,variable in [('Dockerfile','binary-package-cache','K3S_BUILD_PACKAGE'),('Dockerfile.test','kubernetes-package-cache','KUBERNETES_BUILD_PACKAGE')]:
            self.env[variable]='encoding/json'
            body,flags=self.docker_run_body(stage,self.root/'unused-output',dockerfile)
            if dockerfile=='Dockerfile':
                declaration=(SOURCE/dockerfile).read_text().split(' AS '+stage+'\n',1)[1].split('\nFROM ',1)[0]
                self.assertIn('SHELL ["/bin/bash", "-euo", "pipefail", "-c"]',declaration)
            self.assertEqual(flags,['--mount=type=cache,id=gomod,target=/go/pkg/mod','--mount=type=cache,id=gobuild-${TARGETOS}-${TARGETARCH},target=/root/.cache/go-build'])
            for identity in ['', '-n','warm-request-a','warm-request-b']:
                self.env['KUBERNETES_RUN_ID']=identity
                self.log.unlink(missing_ok=True)
                result=self.run_command('bash','-euo','pipefail','-c',body)
                if not identity or identity=='-n':
                    self.assertNotEqual(result.returncode,0,result.stdout);self.assertEqual(self.events(),[])
                    continue
                self.assertEqual(result.returncode,0,result.stderr)
                calls=[r for r in self.events() if r[:2]==['go','build']]
                self.assertEqual(len(calls),1,calls)
                self.assertEqual(calls[0][-1],'encoding/json')
                self.assertEqual(calls[0][calls[0].index('-o')+1],'/dev/null')
                self.assertFalse((self.root/'json').exists())

    def test_native_cache_rejects_invalid_address_before_any_provider(self):
        for value in ["", " ", "-n", "encoding/json fmt", "encoding/json!"]:
            self.log.unlink(missing_ok=True)
            self.env["K3S_BUILD_PACKAGE"] = value
            result = self.run_command("bash", "scripts/build", "cache")
            self.assertEqual(result.returncode, 64, (value,result.stderr))
            self.assertEqual(self.events(), [])


    def test_empty_native_cache_request_refuses_before_any_output_changes(self):
        (self.root / "bin").mkdir()
        (self.root / "bin/k3s").write_text("retained server")
        result = self.run_command("bash", "scripts/build", "cache")
        self.assertEqual(result.returncode, 64, result.stderr)
        self.assertEqual((self.root / "bin/k3s").read_text(), "retained server")
        self.assertEqual(self.events(), [])

    def test_selected_module_download_uses_native_selection_and_errors(self):
        pattern=next(r['match']['commandRegex'] for r in json.loads((SOURCE/'.ai-fleet/tool-execution-policy.json').read_text())['rules'] if r['name']=='k3s-native-construction-segments')
        output=self.root/'module output'
        body,flags=self.docker_run_body('kubernetes-module-download',output)
        self.assertEqual(flags,['--mount=type=bind,source=.,target=${K3S_SOURCE},readonly','--mount=type=cache,id=gomod,target=/go/pkg/mod'])
        self.env.update(KUBERNETES_DOWNLOAD_MODULE='k8s.io/kubernetes',K3S_SOURCE='/fixture/k3s/')
        for identity in ['module-request-a','module-request-b']:
            self.log.unlink(missing_ok=True)
            command=['make','kubernetes-module-download','KUBERNETES_DOWNLOAD_MODULE=k8s.io/kubernetes','KUBERNETES_RUN_ID='+identity]
            result=self.run_command(*command);self.assertEqual(result.returncode,0,result.stderr)
            calls=self.events();self.assertEqual(len(calls),1,calls)
            self.assertRegex('/usr/bin/env BUILDX_BUILDER=ai-fleet-cluster /usr/bin/'+' '.join(command),pattern)
            self.assertIn('KUBERNETES_DOWNLOAD_MODULE=k8s.io/kubernetes',calls[0]);self.assertIn('KUBERNETES_RUN_ID='+identity,calls[0])
            self.assertNotIn('--no-cache-filter',calls[0]);self.assertEqual(calls[0][calls[0].index('--target')+1],'kubernetes-module-download-result')
            self.env['KUBERNETES_RUN_ID']=identity
            result=self.run_command('bash','-euo','pipefail','-c',body);self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual((output/'run-id.txt').read_text(),identity+'\n');self.assertEqual((output/'module.txt').read_text(),'k8s.io/kubernetes\n')
            row=json.loads((output/'module-download.json').read_text());self.assertEqual((row['Path'],row['Version']),('github.com/joshmouch/kubernetes','v1.36.5-k3s1.fleet2'))
        for failure in ['command','json-zero']:
            self.env['TEST_MODULE_FAILURE']=failure
            result=self.run_command('bash','-euo','pipefail','-c',body);self.assertNotEqual(result.returncode,0,result.stdout)
            self.assertEqual(json.loads((output/'module-download.json').read_text())['Error'],'fixture module error')
            self.assertEqual(json.loads(result.stdout)['Error'],'fixture module error')
        self.env.pop('TEST_MODULE_FAILURE')
        # Policy classifies a bounded one-token request; native owners reject
        # special patterns before Docker/Go. Bare dotted roots remain real inputs.
        module='go.opencensus.io';self.log.unlink(missing_ok=True)
        command=['make','kubernetes-module-download','KUBERNETES_DOWNLOAD_MODULE='+module,'KUBERNETES_RUN_ID=bare-module']
        result=self.run_command(*command);self.assertEqual(result.returncode,0,result.stderr)
        calls=self.events();self.assertEqual(len(calls),1,calls)
        self.assertRegex('/usr/bin/env BUILDX_BUILDER=ai-fleet-cluster /usr/bin/'+' '.join(command),pattern)
        self.assertIn('KUBERNETES_DOWNLOAD_MODULE='+module,calls[0])
        self.env.update(KUBERNETES_DOWNLOAD_MODULE=module,KUBERNETES_RUN_ID='bare-module')
        self.log.unlink(missing_ok=True)
        result=self.run_command('bash','-euo','pipefail','-c',body);self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads((output/'module-download.json').read_text())['Path'],module)
        self.assertIn(['go','mod','download','-json',module],self.events())
        self.assertNotIn('(?=',pattern);self.assertNotIn('(?!',pattern)
        for module,classified in [('',False),('-n',False),('all',True),('k8s.io/...',True),('k8s.io/kubernetes@latest',False),('k8s.io/kubernetes other',False)]:
            self.log.unlink(missing_ok=True)
            command=['make','kubernetes-module-download','KUBERNETES_DOWNLOAD_MODULE='+module,'KUBERNETES_RUN_ID=module-request']
            result=self.run_command(*command);self.assertNotEqual(result.returncode,0,result.stdout);self.assertEqual(self.events(),[])
            matched=re.fullmatch(pattern,'/usr/bin/env BUILDX_BUILDER=ai-fleet-cluster /usr/bin/'+' '.join(command))
            self.assertEqual(matched is not None,classified,module)
            self.env['KUBERNETES_DOWNLOAD_MODULE']=module
            result=self.run_command('bash','-euo','pipefail','-c',body);self.assertNotEqual(result.returncode,0,result.stdout);self.assertEqual(self.events(),[])

        self.env['KUBERNETES_DOWNLOAD_MODULE']='k8s.io/kubernetes'
        for identity in ['', '-n']:
            self.log.unlink(missing_ok=True)
            command=['make','kubernetes-module-download','KUBERNETES_DOWNLOAD_MODULE=k8s.io/kubernetes','KUBERNETES_RUN_ID='+identity]
            result=self.run_command(*command);self.assertNotEqual(result.returncode,0,result.stdout);self.assertEqual(self.events(),[])
            self.assertIsNone(re.fullmatch(pattern,'/usr/bin/env BUILDX_BUILDER=ai-fleet-cluster /usr/bin/'+' '.join(command)))
            self.env['KUBERNETES_RUN_ID']=identity
            result=self.run_command('bash','-euo','pipefail','-c',body);self.assertNotEqual(result.returncode,0,result.stdout);self.assertEqual(self.events(),[])

    def test_cache_state_test_graph_keeps_native_variants_without_compiling(self):
        pattern=next(r['match']['commandRegex'] for r in json.loads((SOURCE/'.ai-fleet/tool-execution-policy.json').read_text())['rules'] if r['name']=='k3s-native-construction-segments')
        for identity in ['test-graph-a','test-graph-b']:
            self.log.unlink(missing_ok=True)
            command=['make','kubernetes-cache-state','KUBERNETES_BUILD_PACKAGE=net/http','KUBERNETES_RUN_ID='+identity,'KUBERNETES_TEST_GRAPH=true']
            result=self.run_command(*command)
            self.assertEqual(result.returncode,0,result.stderr)
            calls=self.events();self.assertEqual(len(calls),1,calls)
            self.assertRegex('/usr/bin/env BUILDX_BUILDER=ai-fleet-cluster /usr/bin/'+' '.join(command),pattern)
            self.assertIn('KUBERNETES_TEST_GRAPH=true',calls[0])
            self.assertIn('KUBERNETES_RUN_ID='+identity,calls[0])
            self.assertEqual(calls[0][calls[0].index('--target')+1],'kubernetes-cache-state-result')
            self.assertNotIn('--no-cache',calls[0]);self.assertNotIn('--no-cache-filter',calls[0])
        for mode in ['', 'TRUE', '1', 'maybe']:
            self.log.unlink(missing_ok=True)
            command=['make','kubernetes-cache-state','KUBERNETES_BUILD_PACKAGE=net/http','KUBERNETES_RUN_ID=test-graph','KUBERNETES_TEST_GRAPH='+mode]
            result=self.run_command(*command)
            self.assertNotEqual(result.returncode,0,result.stdout);self.assertEqual(self.events(),[])
            self.assertIsNone(re.fullmatch(pattern,'/usr/bin/env BUILDX_BUILDER=ai-fleet-cluster /usr/bin/'+' '.join(command)))
        self.assertIsNone(re.fullmatch(pattern,'/usr/bin/env BUILDX_BUILDER=ai-fleet-cluster /usr/bin/make kubernetes-cache-packages KUBERNETES_BUILD_PACKAGE=net/http KUBERNETES_RUN_ID=x KUBERNETES_TEST_GRAPH=true'))
        output=self.root/'test graph output'
        body,flags=self.docker_run_body('kubernetes-cache-state',output)
        self.assertEqual(flags,['--network=none','--mount=type=bind,source=.,target=${K3S_SOURCE},readonly','--mount=type=cache,id=gomod,target=/go/pkg/mod,readonly','--mount=type=cache,id=gobuild-${TARGETOS}-${TARGETARCH},target=/root/.cache/go-build'])
        self.provider('cc',"print('fixture compiler identity')\n")
        self.env.update(TEST_CACHE_OBSERVATION_ONLY='yes',KUBERNETES_BUILD_PACKAGE='net/http',KUBERNETES_RUN_ID='test-graph',
                        KUBERNETES_TEST_GRAPH='true',TEST_CACHE_METADATA_DIR=str(self.root/'normal cache metadata'))
        self.log.unlink(missing_ok=True)
        result=self.run_command('bash','-euo','pipefail','-c',body)
        self.assertEqual(result.returncode,0,result.stderr)
        rows=[json.loads(line) for line in (output/'cache-state.json').read_text().splitlines()]
        self.assertEqual(len(rows),7)
        self.assertEqual(rows[3]['TestGoFiles'],['http_test.go']);self.assertEqual(rows[3]['XTestGoFiles'],['external_test.go'])
        self.assertEqual(rows[3]['TestEmbedFiles'],['test-input.bin']);self.assertEqual(rows[3]['XTestEmbedFiles'],['external-input.bin'])
        self.assertEqual(rows[4]['ForTest'],'net/http');self.assertEqual(rows[5]['ForTest'],'net/http')
        self.assertEqual(rows[6],dict(ImportPath='net/http.test'))
        self.assertEqual(json.loads((output/'cache-state-counts.json').read_text()),dict(records=7,inputRecords=1,testGraph=True,forTestRecords=2,requestedForTestRecords=2))
        self.assertTrue(all(c[:2] not in [['go','build'],['go','test'],['go','tool']] for c in self.events()))
        for old,new in [('-test=true','-test=false'),(',ForTest',''),(',TestEmbedFiles',''),('-export=false','-export=true'),('-compiled=false','-compiled=true'),('-cover=false','-cover=true'),('go list -mod=readonly','go test -mod=readonly')]:
            self.log.unlink(missing_ok=True)
            refused=self.run_command('bash','-euo','pipefail','-c',body.replace(old,new))
            self.assertNotEqual(refused.returncode,0,refused.stdout)
        for mode in ['','TRUE','1']:
            self.env['KUBERNETES_TEST_GRAPH']=mode
            self.log.unlink(missing_ok=True)
            refused=self.run_command('bash','-euo','pipefail','-c',body)
            self.assertNotEqual(refused.returncode,0,refused.stdout);self.assertEqual(self.events(),[])
