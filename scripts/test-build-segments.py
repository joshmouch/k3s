#!/usr/bin/env python3
"""Exercise native phase boundaries through standard unittest and shared providers."""
import os
from pathlib import Path
import sys
sys.dont_write_bytecode = True
import json
import re
import shlex
import shutil
import unittest
from native_segment_fixture import OWNERS, SOURCE, NativeSegmentFixture
from native_go_cache_cases import NativeGoCacheCases

NATIVE_SELECTOR_REFUSALS = ('', 'Test name', 'Test;echo', 'Test$(shell echo)', 'Test`echo`', 'Test"quote', 'Test\nOther', "'Test'", '"Test"')


class NativeSegments(NativeSegmentFixture):
    def test_sdk_preparation_precedes_volatile_source_staging(self):
        dockerfile=(SOURCE/'Dockerfile.test').read_text()
        base=dockerfile.split('FROM ${GOLANG} AS test-base\n',1)[1].split('\nFROM ',1)[0]
        sdk=dockerfile.split('FROM test-base AS kubernetes-test-base\n',1)[1].split('\nFROM ',1)[0]
        mods=dockerfile.split('FROM test-base AS test-mods\n',1)[1].split('\nFROM ',1)[0]
        # A whole-source copy in an ancestor also invalidates the child SDK layer.
        self.assertNotRegex(base,r'(?m)^(?:COPY|ADD)\s|--mount=type=bind')
        self.assertEqual(re.findall(r'(?m)^RUN apk[^\n]*',base),['RUN apk -U --no-cache add bash jq'])
        self.assertEqual(re.findall(r'(?m)^RUN apk[^\n]*',sdk),['RUN apk -U --no-cache add build-base git'])
        self.assertLess(sdk.index('RUN apk -U --no-cache add build-base git'),sdk.index('COPY . ${K3S_SOURCE}'))
        for consumer in [sdk,mods]:
            self.assertEqual(re.findall(r'(?m)^COPY \. [^\n]*',consumer),['COPY . ${K3S_SOURCE}'])
        self.assertLess(mods.index('COPY . ${K3S_SOURCE}'),mods.index('COPY ./scripts/test-mods ./scripts/test-mods-test /bin/'))
        self.assertIn('ENTRYPOINT ["/bin/test-mods-test"]',mods)
        self.assertIn('ENV K3S_SOURCE=/go/src/github.com/k3s-io/k3s/\nWORKDIR ${K3S_SOURCE}',base)

    def test_real_make_keeps_six_focus_and_assembled_package_denominators(self):
        rules=json.loads((SOURCE/'.ai-fleet/tool-execution-policy.json').read_text())['rules']
        patterns={r['name']:r['match']['commandRegex'] for r in rules}
        fresh=[]
        for family in ["compile", "list", "focus", "assembled"]:
            selected = []
            for owner, package in OWNERS.items():
                target = "kubernetes-test-"+("" if family == "focus" else family+"-")+owner
                if family in ['focus','assembled']:fresh.append(target)
                for identity in [None] if family in ['compile','list'] else ['owned-request-a','owned-request-b']:
                    self.log.unlink(missing_ok=True)
                    command=['make',target]+(['KUBERNETES_RUN_ID='+identity] if identity else [])
                    result=self.run_command(*command)
                    self.assertEqual(result.returncode,0,result.stderr)
                    calls=self.events(); self.assertEqual(len(calls),1,calls)
                    args=calls[0]
                    key='k3s-native-construction-segments' if family in ['compile','list'] else 'k3s-kubernetes-native-owner-tests' if family=='focus' else 'k3s-kubernetes-native-assembled-tests'
                    self.assertRegex('/usr/bin/env BUILDX_BUILDER=ai-fleet-cluster /usr/bin/'+' '.join(command),patterns[key])
                    self.assertIn('KUBERNETES_TEST_PACKAGE='+package,args)
                    self.assertIn('KUBERNETES_TEST_PACKAGES='+' '.join(OWNERS.values()),args)
                    if owner=='images' and family=='focus':
                        self.assertIn('KUBERNETES_TEST_RUN=^(TestDetectImagesContainerDisappearsBetweenListAndStatus|TestDetectImagesContainerStatusErrorsRemainFailures|TestDetectImagesImageVolumeDisabledDoesNotQueryStatus)$',args)
                    self.assertNotIn('--no-cache-filter',args);self.assertNotIn('--no-cache',args)
                    expected={'compile':'kubernetes-test-compile-result','list':'kubernetes-test-list-result'}.get(family,'kubernetes-test-result')
                    self.assertEqual(args[args.index('--target')+1],expected)
                    if family=='assembled':self.assertIn('KUBERNETES_TEST_RUN=.',args)
                    if identity:self.assertIn('KUBERNETES_RUN_ID='+identity,args)
                    else:self.assertFalse(any(x.startswith('KUBERNETES_RUN_ID=') for x in args))
                    if family=='list':self.assertIsNone(re.fullmatch(patterns[key],'/usr/bin/env BUILDX_BUILDER=ai-fleet-cluster /usr/bin/'+' '.join(command+['KUBERNETES_RUN_ID=unclaimed-list-label'])))
                selected.append(next(x.split("=",1)[1] for x in args if x.startswith("KUBERNETES_TEST_PACKAGE=")))
                self.assertEqual(selected[-1],package)
            self.assertEqual(set(selected),set(OWNERS.values()))
        for target in ['kubernetes-test-images-other','kubernetes-test-compile-images-other','kubernetes-test-list-images-other','kubernetes-test-assembled-images-other']:
            self.log.unlink(missing_ok=True)
            command=['make',target,'KUBERNETES_RUN_ID=owned-request-a']
            refused=self.run_command(*command)
            self.assertNotEqual(refused.returncode,0,refused.stdout)
            self.assertEqual(self.events(),[])
            self.assertFalse(any(re.fullmatch(p,'/usr/bin/env BUILDX_BUILDER=ai-fleet-cluster /usr/bin/'+' '.join(command)) for p in patterns.values()))
        for identity in ['owned-request-a','owned-request-b']:
            self.log.unlink(missing_ok=True)
            command=['make','kubernetes-test-readiness','KUBERNETES_RUN_ID='+identity]
            result=self.run_command(*command)
            self.assertEqual(result.returncode,0,result.stderr)
            calls=self.events(); self.assertEqual(len(calls),1,calls)
            args=calls[0]
            self.assertRegex('/usr/bin/env BUILDX_BUILDER=ai-fleet-cluster /usr/bin/'+' '.join(command),patterns['k3s-native-construction-segments'])
            self.assertNotIn('--no-cache-filter',args);self.assertNotIn('--no-cache',args)
            self.assertIn('KUBERNETES_RUN_ID='+identity,args)
            self.assertEqual(args[args.index('--target')+1],'kubernetes-test-readiness-result')
        for target in ['kubernetes-test-readiness',*fresh]:
            for identity in [None,'-n']:
                self.log.unlink(missing_ok=True)
                command=['make',target]+(['KUBERNETES_RUN_ID='+identity] if identity else [])
                result=self.run_command(*command)
                self.assertNotEqual(result.returncode,0,result.stdout)
                self.assertEqual(self.events(),[])
                self.assertFalse(any(re.fullmatch(p,'/usr/bin/env BUILDX_BUILDER=ai-fleet-cluster /usr/bin/'+' '.join(command)) for p in patterns.values()))
        output=self.root/'readiness output'
        body,flags=self.docker_run_body('kubernetes-test-readiness',output)
        self.assertEqual(flags,['--mount=type=cache,id=gomod,target=/go/pkg/mod','--mount=type=cache,id=gobuild-${TARGETOS}-${TARGETARCH},target=/root/.cache/go-build'])
        self.env.update(x.split('=',1) for x in args if x.startswith(('KUBERNETES_TEST_MEMORY_BYTES=','KUBERNETES_TEST_CPU_PERIOD=','KUBERNETES_TEST_CPU_QUOTA=')))
        self.provider('cat',"import os,sys\nvalues={'/sys/fs/cgroup/memory.max':os.environ['KUBERNETES_TEST_MEMORY_BYTES'],'/sys/fs/cgroup/memory.swap.max':'0','/sys/fs/cgroup/cpu.max':os.environ['KUBERNETES_TEST_CPU_QUOTA']+' '+os.environ['KUBERNETES_TEST_CPU_PERIOD']}\nprint(values.get(sys.argv[1],'fixture native metadata'))\n")
        self.provider('cc',"print('fixture compiler identity')\n")
        (self.root/'scripts/test-mods-test').write_text('echo fixture module-policy provider\n')
        for identity in ['owned-request-a','owned-request-b','','-n']:
            self.env['KUBERNETES_RUN_ID']=identity
            self.log.unlink(missing_ok=True)
            result=self.run_command('bash','-euo','pipefail','-c',body)
            if identity and identity!='-n':
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertEqual((output/'run-id.txt').read_text(),identity+'\n')
            else:
                self.assertNotEqual(result.returncode,0,result.stdout)
                self.assertEqual(self.events(),[])

    def test_real_make_plugin_outline_reuses_inputs_and_has_its_own_policy(self):
        rules=json.loads((SOURCE/'.ai-fleet/tool-execution-policy.json').read_text())['rules']
        rule=next(r for r in rules if r['name']=='k3s-kubernetes-plugin-outline')
        self.assertEqual((rule['deadlineMilliseconds'],rule['cleanupMilliseconds'],rule['memoryMegabytes'],rule['cpuCores']),(20000,1000,512,2))
        self.assertEqual([r['deadlineMilliseconds'] for r in rules if r is not rule],[40000]*4)
        pattern=rule['match']['commandRegex']
        prefix='/usr/bin/env BUILDX_BUILDER=ai-fleet-cluster /usr/bin/'
        target='kubernetes-test-outline-plugin'
        for identity in ['root8-v16-plugin-focus-1','owned-outline-b']:
            self.log.unlink(missing_ok=True)
            focused=self.run_command('make','kubernetes-test-plugin','KUBERNETES_RUN_ID='+identity)
            self.assertEqual(focused.returncode,0,focused.stderr)
            focus_calls=self.events();self.assertEqual(len(focus_calls),1,focus_calls)
            expected=focus_calls[0][:]
            for flag in ['--metadata-file','--output']:
                position=expected.index(flag);del expected[position:position+2]
            expected[-1:-1]=['--call=outline']
            self.log.unlink(missing_ok=True)
            command=['make',target,'KUBERNETES_RUN_ID='+identity]
            outlined=self.run_command(*command)
            self.assertEqual(outlined.returncode,0,outlined.stderr)
            calls=self.events();self.assertEqual(len(calls),1,calls)
            self.assertEqual(calls[0],expected)
            self.assertRegex(prefix+' '.join(command),pattern)
            self.assertIn('KUBERNETES_TEST_PACKAGE='+OWNERS['plugin'],calls[0])
            self.assertIn('KUBERNETES_TEST_PACKAGES='+' '.join(OWNERS.values()),calls[0])
            self.assertIn('KUBERNETES_TEST_RUN=Test',calls[0])
            self.assertEqual(calls[0][calls[0].index('--target')+1],'kubernetes-test-result')
            for flag in ['--no-cache','--no-cache-filter','--output','--push','--load','--metadata-file']:
                self.assertNotIn(flag,calls[0])
        for suffix in [[],['KUBERNETES_RUN_ID=-n'],['KUBERNETES_RUN_ID=two words'],['KUBERNETES_RUN_ID=ok','kubernetes-test-plugin']]:
            self.log.unlink(missing_ok=True)
            command=['make',target,*suffix]
            result=self.run_command(*command)
            self.assertNotEqual(result.returncode,0,result.stdout)
            self.assertEqual(self.events(),[])
            self.assertIsNone(re.fullmatch(pattern,prefix+' '.join(command)))
        for altered in [target+'-other','kubernetes-test-outline-admission','kubernetes-test-plugin']:
            self.assertIsNone(re.fullmatch(pattern,prefix+'make '+altered+' KUBERNETES_RUN_ID=ok'))
        self.assertIsNone(re.fullmatch(pattern,prefix+'make '+target+' KUBERNETES_RUN_ID=ok EXTRA=1'))
        self.provider('docker',"import json,os,sys\nwith open(os.environ['TEST_SEGMENT_LOG'],'a') as f:f.write(json.dumps(sys.argv[1:])+'\\n')\nsys.exit(47)\n")
        self.log.unlink(missing_ok=True)
        failed=self.run_command('make',target,'KUBERNETES_RUN_ID=failed-outline')
        self.assertNotEqual(failed.returncode,0,failed.stdout)
        self.assertIn('Error 47',failed.stderr)
        self.assertEqual(len(self.events()),1)

    def test_actual_compiled_test_stage_uses_package_directory_and_keeps_failure(self):
        package = self.root / "selected module" / "pkg" / "controller" / "cronjob"
        (package / "testdata").mkdir(parents=True)
        (package / "testdata/runtime.txt").write_text("package-relative fixture")
        self.env.update(TEST_SEGMENT_PACKAGE_DIR=str(package), KUBERNETES_TEST_PACKAGE=OWNERS["cronjob"],
                        KUBERNETES_TEST_RUN="TestFixture",KUBERNETES_RUN_ID="owned-test-request",
                        KUBERNETES_TEST_PACKAGES=' '.join(OWNERS.values()),TEST_SEGMENT_COMPILE_FAIL='no',TEST_SEGMENT_LIST_EMPTY='no')
        output = self.root / "test-output"
        template = self.root / "compiled-provider.py"
        template.write_text("#!/usr/bin/env python3\n"
            "import json,os,pathlib,sys\n"
            "actual=pathlib.Path.cwd(); expected=pathlib.Path(os.environ['TEST_SEGMENT_PACKAGE_DIR'])\n"
            "assert actual.samefile(expected), f'wrong package directory: actual={actual} expected={expected}'\n"
            "assert pathlib.Path('testdata/runtime.txt').read_text()=='package-relative fixture'\n"
            "if '-test.list=.' in sys.argv:\n"
            " if os.environ.get('TEST_SEGMENT_LIST_FAIL')=='yes':sys.exit(47)\n"
            " if os.environ.get('TEST_SEGMENT_LIST_EMPTY')!='yes':print('TestFixture')\n"
            " sys.exit(0)\n"
            "failed=os.environ.get('TEST_SEGMENT_TEST_FAIL')=='yes'\n"
            "print(json.dumps(dict(Action='fail' if failed else 'pass',Test='TestFixture')))\n"
            "sys.exit(47 if failed else 0)\n")
        self.env['TEST_SEGMENT_COMPILE_TEMPLATE']=str(template)
        compile_body,compile_flags=self.docker_run_body('kubernetes-test-compile',output)
        self.assertEqual(compile_flags,['--mount=type=cache,id=gomod,target=/go/pkg/mod','--mount=type=cache,id=gobuild-${TARGETOS}-${TARGETARCH},target=/root/.cache/go-build'])
        compiled=self.run_command('bash','-euo','pipefail','-c',compile_body)
        self.assertEqual(compiled.returncode,0,compiled.stderr)
        prefix='native-kubernetes-compile phase='
        self.assertEqual([line for line in compiled.stderr.splitlines() if line.startswith(prefix)],
                         [prefix+p for p in ['prepare','module-identities','package-dir','go-test-c','complete']])
        binary=output/'package.test'
        self.assertTrue(binary.is_file());self.assertFalse((output/'test-list.txt').exists())
        self.assertEqual((output/'package-dir.txt').read_text(),str(package)+'\n')
        compile_metadata={'packages.txt','go-version.txt','module-identities.json'}
        metadata=compile_metadata|{'test-list.txt'}
        compile_export=self.root/'compile export'
        self.assertEqual(self.docker_copy_output('kubernetes-test-compile-result',output,compile_export),'kubernetes-test-compile')
        self.assertEqual({p.name for p in compile_export.iterdir()},compile_metadata)
        for name in compile_metadata:self.assertEqual((compile_export/name).read_bytes(),(output/name).read_bytes())
        self.assertFalse((compile_export/'package.test').exists());self.assertEqual(binary.read_bytes(),template.read_bytes())
        for flag,phase in [('TEST_SEGMENT_MODULE_IDENTITIES_FAIL','module-identities'),('TEST_SEGMENT_DIR_EMPTY','package-dir'),
                           ('TEST_SEGMENT_COMPILE_FAIL','go-test-c')]:
            self.env[flag]='yes'
            refused_output=self.root/flag
            refused_body,_=self.docker_run_body('kubernetes-test-compile',refused_output)
            refused=self.run_command('bash','-euo','pipefail','-c',refused_body)
            self.assertNotEqual(refused.returncode,0,refused.stdout)
            markers=[line for line in refused.stderr.splitlines() if line.startswith(prefix)]
            self.assertEqual(markers[-1],prefix+phase,refused.stderr)
            self.assertNotIn(prefix+'complete',markers)
            self.assertFalse((refused_output/'package.test').exists())
            self.env[flag]='no'
        for kind in ['missing','empty','not-executable']:
            self.env['TEST_SEGMENT_COMPILE_OUTPUT']=kind
            refused_output=self.root/kind
            refused_body,_=self.docker_run_body('kubernetes-test-compile',refused_output)
            refused=self.run_command('bash','-euo','pipefail','-c',refused_body)
            self.assertNotEqual(refused.returncode,0,refused.stdout)
            self.assertNotIn(prefix+'complete',refused.stderr)
        self.env.pop('TEST_SEGMENT_COMPILE_OUTPUT')
        dockerfile=(SOURCE/'Dockerfile.test').read_text()
        self.assertIn('FROM kubernetes-test-compile AS kubernetes-test-list\n',dockerfile)
        self.assertIn('FROM kubernetes-test-list AS kubernetes-test\n',dockerfile)
        list_body,list_flags=self.docker_run_body('kubernetes-test-list',output)
        self.assertEqual(list_flags,['--mount=type=cache,id=gomod,target=/go/pkg/mod'])
        list_prefix='native-kubernetes-list phase='
        listed=self.run_command('bash','-euo','pipefail','-c',list_body)
        self.assertEqual(listed.returncode,0,listed.stderr)
        self.assertEqual([line for line in listed.stderr.splitlines() if line.startswith(list_prefix)],
                         [list_prefix+p for p in ['package-dir','test-list','complete']])
        self.assertEqual((output/'test-list.txt').read_text(),'TestFixture\n')
        self.assertEqual(binary.read_bytes(),template.read_bytes())
        list_export=self.root/'list export'
        self.assertEqual(self.docker_copy_output('kubernetes-test-list-result',output,list_export),'kubernetes-test-list')
        self.assertEqual({p.name for p in list_export.iterdir()},metadata)
        for name in metadata:self.assertEqual((list_export/name).read_bytes(),(output/name).read_bytes())
        self.assertFalse((list_export/'package.test').exists())
        for flag in ['TEST_SEGMENT_LIST_EMPTY','TEST_SEGMENT_LIST_FAIL']:
            self.env[flag]='yes'
            inherited=self.root/flag
            inherited.mkdir()
            # Simulate FROM's immutable parent inside the owned synthetic fixture.
            for name in compile_metadata|{'package.test','package-dir.txt'}:shutil.copy2(output/name,inherited/name)
            refused_body,_=self.docker_run_body('kubernetes-test-list',inherited)
            refused=self.run_command('bash','-euo','pipefail','-c',refused_body)
            self.assertNotEqual(refused.returncode,0,refused.stdout)
            markers=[line for line in refused.stderr.splitlines() if line.startswith(list_prefix)]
            self.assertEqual(markers[-1],list_prefix+'test-list',refused.stderr)
            self.assertNotIn(list_prefix+'complete',markers)
            self.assertEqual((inherited/'test-list.txt').read_text(),'')
            self.env[flag]='no'
        body,flags = self.docker_run_body("kubernetes-test",output)
        self.assertEqual(flags,["--mount=type=cache,id=gomod,target=/go/pkg/mod"])
        self.env['KUBERNETES_RUN_ID']=''
        self.log.unlink(missing_ok=True)
        refused=self.run_command('bash','-euo','pipefail','-c',body)
        self.assertNotEqual(refused.returncode,0,refused.stdout)
        self.assertEqual(self.events(),[])
        self.env['KUBERNETES_RUN_ID']='owned-test-request'
        directory_fact=output/'package-dir.txt'
        original_directory=directory_fact.read_bytes()
        for raw in [None,b'']:
            if raw is None:directory_fact.unlink()
            else:directory_fact.write_bytes(raw)
            for selected_body in [list_body,body]:
                self.log.unlink(missing_ok=True)
                refused=self.run_command('bash','-euo','pipefail','-c',selected_body)
                self.assertNotEqual(refused.returncode,0,refused.stdout)
                self.assertEqual(self.events(),[])
            directory_fact.write_bytes(original_directory)
        # Filesystem identity permits the native /var alias but not a different
        # package with matching relative contents, for both inventory and tests.
        alias = self.root / "selected package alias"
        alias.symlink_to(package, target_is_directory=True)
        for selected in [package, alias]:
            self.env["TEST_SEGMENT_GO_DIR"] = str(selected)
            refreshed=self.run_command('bash','-euo','pipefail','-c',compile_body)
            self.assertEqual(refreshed.returncode,0,refreshed.stderr)
            self.assertEqual(directory_fact.read_text(),str(selected)+'\n')
            listed=self.run_command('bash','-euo','pipefail','-c',list_body)
            self.assertEqual(listed.returncode,0,listed.stderr)
            self.assertEqual((output/'test-list.txt').read_text(),'TestFixture\n')
            for failed in [False, True]:
                self.env["TEST_SEGMENT_TEST_FAIL"] = "yes" if failed else "no"
                self.log.unlink(missing_ok=True)
                result = self.run_command("bash", "-euo", "pipefail", "-c", body)
                if failed:
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                else:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    exported=self.root/('test export '+str(selected==alias))
                    self.assertEqual(self.docker_copy_output('kubernetes-test-result',output,exported),'kubernetes-test')
                    self.assertEqual({p.name for p in exported.iterdir()},metadata|{'run-id.txt','test-selection.txt','go-test.json'})
                    self.assertFalse((exported/'package.test').exists())
                    for name in metadata|{'run-id.txt','test-selection.txt','go-test.json'}:self.assertEqual((exported/name).read_bytes(),(output/name).read_bytes())
                records = [json.loads(line) for line in (output / "go-test.json").read_text().splitlines()]
                self.assertEqual(records, [dict(Action="fail" if failed else "pass", Test="TestFixture")])
                self.assertEqual((output / "test-selection.txt").read_text(), "TestFixture\n")
                self.assertEqual((output/'run-id.txt').read_text(),'owned-test-request\n')
                self.assertTrue(binary.is_file());self.assertFalse(any(c[:2] in [['go','test'],['go','list']] for c in self.events()))
        wrong = self.root / "wrong module" / "pkg" / "controller" / "cronjob"
        (wrong / "testdata").mkdir(parents=True)
        (wrong / "testdata/runtime.txt").write_text("package-relative fixture")
        self.env.update(TEST_SEGMENT_GO_DIR=str(wrong), TEST_SEGMENT_TEST_FAIL="no")
        refreshed=self.run_command('bash','-euo','pipefail','-c',compile_body)
        self.assertEqual(refreshed.returncode,0,refreshed.stderr)
        listed=self.run_command('bash','-euo','pipefail','-c',list_body)
        self.assertNotEqual(listed.returncode,0,listed.stdout)
        self.assertIn('wrong package directory',listed.stderr)
        self.assertEqual((output/'test-list.txt').read_text(),'')
        self.log.unlink(missing_ok=True)
        result = self.run_command("bash", "-euo", "pipefail", "-c", body)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("wrong package directory", result.stderr)
        self.assertEqual((output / "go-test.json").read_text(), "")
        self.assertEqual((output / "test-selection.txt").read_text(), "TestFixture\n")


    def test_unknown_component_refuses_before_removing_existing_outputs(self):
        for script in ["build", "download", "package-cli"]:
            sentinel = self.root / "bin" / "k3s"
            sentinel.parent.mkdir(exist_ok=True)
            sentinel.write_text("retained unique fixture bytes")
            result = self.run_command("bash", "scripts/"+script, "not-a-component")
            self.assertEqual(result.returncode, 64, result.stderr)
            self.assertEqual(sentinel.read_text(), "retained unique fixture bytes")
        self.assertEqual(self.events(), [])

    def test_k3s_component_preserves_cni_shim_and_runc_outputs(self):
        retained = ["bin/cni", "bin/containerd-shim-runc-v2", "bin/runc"]
        for name in retained:
            p = self.root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(name)
            p.chmod(0o755)
        for directory in ["manifests", "build/static", "pkg/deploy/embed", "pkg/static/embed"]:
            (self.root / directory).mkdir(parents=True, exist_ok=True)
        (self.root / "manifests/chart.yaml").write_text("chart source")
        (self.root / "build/static/rootfs").write_text("root source")
        result = self.run_command("bash", "scripts/build", "k3s")
        self.assertEqual(result.returncode, 0, result.stderr)
        for name in retained:
            self.assertEqual((self.root / name).read_text(), name)
        self.assertTrue((self.root / "bin/k3s-server").is_symlink())
        builds = [x for x in self.events() if x[:2] == ["go", "build"]]
        self.assertEqual(len(builds), 1, builds)
        self.assertEqual(builds[0][-1], "./cmd/server")

    def test_chart_component_preserves_other_download_units(self):
        retained = ["build/src/github.com/opencontainers/runc/sentinel",
                    "build/src/github.com/containerd/containerd/sentinel"]
        for name in retained:
            p = self.root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(name)
        (self.root / "manifests").mkdir()
        (self.root / "manifests/chart.yaml").write_text("kind: HelmChart\n")
        result = self.run_command("bash", "scripts/download", "charts")
        self.assertEqual(result.returncode, 0, result.stderr)
        for name in retained:
            self.assertEqual((self.root / name).read_text(), name)
        self.assertEqual((self.root / "build/static/charts/chart-1.0.0.tgz").read_text(), "chart bytes")

    def test_multicall_binary_phase_preserves_prepared_native_data(self):
        for directory in ["build/data", "dist/artifacts", "pkg/data/embed", "bin"]:
            (self.root / directory).mkdir(parents=True, exist_ok=True)
        (self.root / "build/data/fixture.tar.zst").write_text("prepared native data")
        (self.root / "bin/cni").write_text("retained cni")
        result = self.run_command("bash", "scripts/package-cli", "binary")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / "build/data/fixture.tar.zst").read_text(), "prepared native data")
        self.assertEqual((self.root / "pkg/data/embed/fixture.tar.zst").read_text(), "prepared native data")
        self.assertEqual((self.root / "bin/cni").read_text(), "retained cni")
        builds = [x for x in self.events() if x[:2] == ["go", "build"]]
        self.assertEqual(len(builds), 1, builds)
        self.assertEqual(builds[0][-1], "./cmd/k3s")


    def test_real_make_native_test_selector_preserves_data_and_policy(self):
        policy=json.loads((SOURCE/'.ai-fleet/tool-execution-policy.json').read_text())
        rules=policy['rules']
        for target,name in [('kubernetes-test-kubelet','k3s-kubernetes-native-owner-tests'),
                            ('kubernetes-test-assembled-kubelet','k3s-kubernetes-native-assembled-tests')]:
            rule=next(r for r in rules if r['name']==name);pattern=rule['match']['commandRegex']
            self.assertEqual((rule['deadlineMilliseconds'],rule['cleanupMilliseconds'],rule['memoryMegabytes'],rule['cpuCores']),(40000,2000,2048,2))
            base=['/usr/bin/env','BUILDX_BUILDER=ai-fleet-cluster','/usr/bin/make',target]
            default=base+['KUBERNETES_RUN_ID=default-selection']
            self.log.unlink(missing_ok=True)
            result=self.run_command(*default)
            self.assertEqual(result.returncode,0,result.stderr)
            calls=self.events();self.assertEqual(len(calls),1,calls);default_args=calls[0]
            self.assertRegex(' '.join(default),pattern)
            if 'assembled' in target:self.assertIn('KUBERNETES_TEST_RUN=.',default_args)
            for selector in ['TestPodVolumeDeadlineUnmount','^Test(DeferredAdmission|PodVolumeDeadline)','^TestPodVolumeDeadlineUnmount$']:
                # Finite-command selects policy over executable/argv joined with spaces.
                # Shell quotation is rendering only; Make still consumes doubled dollars.
                native_selector=selector.replace('$','$$')
                argv=base+['KUBERNETES_TEST_RUN='+native_selector,'KUBERNETES_RUN_ID=selected-cases']
                command=' '.join(argv)
                self.assertRegex(command,pattern)
                self.log.unlink(missing_ok=True)
                result=self.run_command(*argv)
                self.assertEqual(result.returncode,0,result.stderr)
                calls=self.events();self.assertEqual(len(calls),1,calls)
                expected=default_args[:]
                expected=[('KUBERNETES_TEST_RUN='+selector) if x.startswith('KUBERNETES_TEST_RUN=') else
                          'KUBERNETES_RUN_ID=selected-cases' if x.startswith('KUBERNETES_RUN_ID=') else x for x in expected]
                self.assertEqual(calls[0],expected)
                self.assertIn('KUBERNETES_TEST_PACKAGE='+OWNERS['kubelet'],calls[0])
                self.assertIn('KUBERNETES_TEST_PACKAGES='+' '.join(OWNERS.values()),calls[0])
                self.assertNotIn('--no-cache',calls[0]);self.assertNotIn('--no-cache-filter',calls[0])
                if selector.endswith('$'):
                    # The same argv survives an ordinary shell rendering, without
                    # admitting quote characters as part of a structured argument.
                    self.log.unlink(missing_ok=True)
                    rendered=shlex.join(argv)
                    result=self.run_command('bash','-euo','pipefail','-c',rendered)
                    self.assertEqual(result.returncode,0,result.stderr)
                    self.assertEqual(self.events(),[expected])
                    self.assertIsNone(re.fullmatch(pattern,rendered))
                    for invalid in [selector,native_selector+'$']:
                        raw=' '.join(base+['KUBERNETES_TEST_RUN='+invalid,'KUBERNETES_RUN_ID=selected-cases'])
                        self.assertIsNone(re.fullmatch(pattern,raw))
            for value in NATIVE_SELECTOR_REFUSALS:
                command=' '.join(base+['KUBERNETES_TEST_RUN='+value,'KUBERNETES_RUN_ID=selected-cases'])
                self.assertIsNone(re.fullmatch(pattern,command),value)
            valid=' '.join(base+['KUBERNETES_TEST_RUN=^Test(PodVolume|ListVolumes)','KUBERNETES_RUN_ID=selected-cases'])
            for command in [valid+' EXTRA=1',valid+' kubernetes-test-plugin',valid.replace('-kubelet','-kubelet-other'),
                            valid.replace('KUBERNETES_RUN_ID=selected-cases','KUBERNETES_RUN_ID=-n')]:
                self.assertIsNone(re.fullmatch(pattern,command))



    def test_whole_policy_uses_installed_parser_and_structured_selection(self):
        node=os.environ.get('TEST_POLICY_NODE');owner=os.environ.get('TEST_POLICY_OWNER_PACKAGE_JSON')
        self.assertTrue(node and Path(node).is_file(),'TEST_POLICY_NODE must name the selected native Node executable')
        self.assertTrue(owner and Path(owner).is_file(),'TEST_POLICY_OWNER_PACKAGE_JSON must name the installed policy package')
        js=r"""import assert from 'node:assert/strict';
import {createRequire} from 'node:module';import {readFileSync} from 'node:fs';import {pathToFileURL} from 'node:url';import {createHash} from 'node:crypto';
const [file,owner,cwd,invalidJSON]=process.argv.slice(1),req=createRequire(owner);
const parserPath=req.resolve('@ai-fleet/tool-execution-runtime-node/policy-parse'),selectorPath=req.resolve('@ai-fleet/tool-execution-runtime-node/output-run-policy');
const {parseToolExecutionPolicy}=await import(pathToFileURL(parserPath).href),{selectAiFleetExecutionPolicy}=await import(pathToFileURL(selectorPath).href);
const raw=JSON.parse(readFileSync(file,'utf8')),policy=parseToolExecutionPolicy(raw),base=['/usr/bin/env','BUILDX_BUILDER=ai-fleet-cluster','/usr/bin/make'];
const owners=['admission','plugin','device-manager','allocation','kubelet','cronjob','images'];
const expected=['k3s-native-module-construction','k3s-native-construction-segments','k3s-kubernetes-native-owner-tests','k3s-kubernetes-native-assembled-tests','k3s-kubernetes-plugin-outline'];
assert.deepEqual(policy.rules.map(r=>r.name),expected);
function select(a){return selectAiFleetExecutionPolicy({policy,policySource:file,platform:'darwin',command:a.join(' '),cwd,invocation:{executable:a[0],argv:a.slice(1)}});}
const cases=[{row:0,a:['/usr/bin/env','GOTOOLCHAIN=go1.26.8','/usr/bin/make','deps']},{row:1,a:[...base,'kubernetes-test-base']},{row:4,a:[...base,'kubernetes-test-outline-plugin','KUBERNETES_RUN_ID=policy-control']}];
for(const name of owners){for(const kind of ['compile','list'])cases.push({row:1,a:[...base,'kubernetes-test-'+kind+'-'+name]});for(const [row,prefix] of [[2,'kubernetes-test-'],[3,'kubernetes-test-assembled-']])cases.push({row,a:[...base,prefix+name,'KUBERNETES_TEST_RUN=^Test(PodVolume|DeferredAdmission)$$','KUBERNETES_RUN_ID=policy-control']});}
const selected=cases.map(({row,a})=>{const s=select(a),r=policy.rules[row];assert.equal(s.ruleName,r.name);for(const k of ['executorBinding','deadlineMilliseconds','cleanupMilliseconds','maxOutputMegabytes','memoryMegabytes','cpuCores'])assert.equal(s[k],r[k],k);return {ruleName:s.ruleName,argv:a,binding:s.executorBinding};});
let negativeCount=0;const refuse=a=>{assert.throws(()=>select(a));negativeCount++;};
for(const target of ['kubernetes-test-kubelet','kubernetes-test-assembled-kubelet']){
 for(const value of [...JSON.parse(invalidJSON),'^TestX$','^TestX$$$'])refuse([...base,target,'KUBERNETES_TEST_RUN='+value,'KUBERNETES_RUN_ID=policy-control']);
 for(const suffix of [['EXTRA=1'],['kubernetes-test-plugin']])refuse([...base,target,'KUBERNETES_RUN_ID=policy-control',...suffix]);
}
for(const [target,args] of [['kubernetes-test-list-kubelet',[]],['kubernetes-test-outline-plugin',['KUBERNETES_RUN_ID=policy-control']]])refuse([...base,target,...args,'EXTRA=1']);
const missing={...raw};delete missing.$schema;assert.throws(()=>parseToolExecutionPolicy(missing));assert.throws(()=>parseToolExecutionPolicy({...raw,unknownPolicyField:true}));
for(let i=0;i<raw.rules.length;i++){const p=structuredClone(raw);p.rules[i].executorBinding='uninstalled-policy-control-binding';assert.throws(()=>parseToolExecutionPolicy(p));}
console.log(JSON.stringify({kind:'canonical-public-policy-component-control',node:process.execPath,nodeVersion:process.version,owner,parserPath,parserSHA256:createHash('sha256').update(readFileSync(parserPath)).digest('hex'),selectorPath,selectorSHA256:createHash('sha256').update(readFileSync(selectorPath)).digest('hex'),parsedRuleCount:policy.rules.length,selected,negativeCount,missingSchemaRejected:true,unknownFieldsRejected:true,unknownBindingsRejected:raw.rules.length,nativeAdmission:false}));
"""
        result=self.run_command(node,'--input-type=module','-e',js,str(SOURCE/'.ai-fleet/tool-execution-policy.json'),owner,str(SOURCE),json.dumps(NATIVE_SELECTOR_REFUSALS))
        self.assertEqual(result.returncode,0,result.stderr)
        value=json.loads(result.stdout);self.assertEqual(value['parsedRuleCount'],5)
        self.assertEqual(len(value['selected']),31);self.assertEqual(value['negativeCount'],28)
        self.assertFalse(value['nativeAdmission']);print(result.stdout,end='')


if __name__ == "__main__":
    unittest.main(verbosity=2, failfast=True)
