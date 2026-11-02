# Native test selection

`KUBERNETES_TEST_RUN` is the existing Make input for Go's native test selector.
The focus targets and `kubernetes-test-assembled-<owner>` supply ordinary
target-specific defaults, without `override`. A command-line assignment takes
precedence. The shared Make recipe forwards that value as one Buildx argument;
the test stage passes it as the quoted value of `-test.run` on the same compiled
binary through native `go tool test2json`.

```sh
/usr/bin/env BUILDX_BUILDER=ai-fleet-cluster /usr/bin/make kubernetes-test-assembled-kubelet 'KUBERNETES_TEST_RUN=^TestPodVolumeDeadlineUnmount$$' KUBERNETES_RUN_ID=root8-kubelet-unmount-1
```

GNU Make expands command-line variable data after the shell has parsed it.
Single shell quotes preserve the argument for Make; they do not suppress Make's
dollar expansion. The caller therefore encodes each logical Go `$` as native
Make `$$` before rendering the complete assignment with normal shell quoting.
The example supplies `^TestPodVolumeDeadlineUnmount$$` to Make and forwards the
exact logical Go selector `^TestPodVolumeDeadlineUnmount$`. The retained native
Make dry run qualifies that boundary; the permanent actual Make-to-Docker
provider control requires the logical single anchor exactly.

The project policy uses the canonical `ai-fleet/tool-execution-policy/v1`
schema. Its focus/full rules match the finite execution owner's structured
executable/argv projection, joined with spaces for command classification.
Supply each assignment as one argv string; shell quote characters are not part
of that data. For example, the argv element is
`KUBERNETES_TEST_RUN=^TestPodVolumeDeadlineUnmount$$`. The shell example above
renders that same argument with single quotes only to cross the shell parser.

The policy admits ASCII letters/digits/underscore and regex punctuation, with
an optional encoded terminal dollar pair. Raw single or triple terminal dollars,
literal quotes, substitutions, extra arguments and additional Make targets do
not match this command shape. Native Go owns regex semantics. The source-owned
target defaults retain their existing Make syntax; no producer `value` override
or second expansion mechanism is added.

The optional selector precedes `KUBERNETES_RUN_ID` in the admitted command shape.
Without it, every existing focus default and the assembled default `.` remains
unchanged. Neither Make nor Dockerfile behavior changed for this capability.
The same seven package mappings, race/CGO/compiler/module profile, normal cache
owners, immutable compile/list dependency and native test-body flags remain.
The existing 40-second work plus two-second cleanup class is unchanged; the
caller still composes its transport and cleanup within a total of 60 seconds.

Use the actual native `test-list.txt` for the selected constructor/module as the
population. When partitioning a package, compare the union of selected native
top-level names with that inventory and report omissions/overlap explicitly.
Existing test source-file ownership supplies meaningful families; no new
product registry or selector derives a substitute population. A selected
top-level test retains the normal native framework's subtests. Separate requests
reset process initialization, so partitioned coverage leaves whole-process
ordering/interference as a distinct unchecked relation.

The retained fleet10 Kubelet assembled attempt has 151 top-level starts,150
passes, no recorded failures/skips and incomplete `TestPodVolumeDeadlineUnmount`
before the outer deadline. Its compile/list parents were cached. Those partial
events do not establish a complete package or 176-test acceptance. They support
a narrower native-framework diagnostic and measured source-family partitions,
without changing the wall, dropping the incomplete case, or replaying the same
full request.

The permanent existing fixture entry adds
`NativeSegments.test_real_make_native_test_selector_preserves_data_and_policy`.
It executes actual structured argv through Make and the shared disposable Docker
provider, also checks ordinary shell rendering of the anchored selector, proves
exact forwarding and otherwise identical arguments, checks default full selection,
and covers policy quote/data near misses. All16 earlier method bodies remain. These source controls do not execute
a Kubernetes case or qualify the real selected family outcomes.

The three 40-second work plus two-second cleanup classes select the existing
native supervised finite executor. Their original limits, names and command
populations are unchanged. The installed Conflux 1.1.39 projection accepts at
most one second of cleanup, so those classes cannot be represented by that
binding. The separate 20-second outline class retains its one-second cleanup
and Conflux binding. Normal finite-command preparation, execution and retained
cleanup remain the admission owner; a Make run label supplies no authority.

`NativeSegments.test_whole_policy_uses_installed_parser_and_structured_selection`
uses the installed public policy parser and provider-neutral structured-input
selector. Its caller supplies `TEST_POLICY_NODE` with the selected native Node
executable and `TEST_POLICY_OWNER_PACKAGE_JSON` with the installed policy
package manifest. Missing bindings fail the control. It parses the entire five
rule document, selects the declared rules for all seven owner mappings, checks
their unchanged limits, and rejects malformed schemas, fields, bindings and
selector/argv near misses. This is a source-input control; it creates no finite
operation and supplies no native execution or cleanup authority. The original
17 fixture methods remain, giving 18 methods with this coupled control.
