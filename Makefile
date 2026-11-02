GO_FILES ?= $$(find . -name '*.go')
SHELL := /bin/bash


.PHONY: docker.sock
docker.sock:
	while ! docker version 1>/dev/null; do sleep 1; done

.PHONY: deps
deps:
	go mod tidy

.DEFAULT_GOAL := ci

.PHONY: $(TARGETS)

build/data:
	mkdir -p $@

.PHONY: binary-size-check
binary-size-check:
	scripts/binary_size_check.sh

.PHONY: image-scan
image-scan:
	scripts/image_scan.sh $(IMAGE)

format:
	gofmt -s -l -w $(GO_FILES)
	goimports -w $(GO_FILES)

.PHONY: tag-image-latest
tag-image-latest:
	scripts/tag-image-latest

.PHONY: validate
validate:
	docker buildx build \
		--build-arg="SKIP_VALIDATE=$(SKIP_VALIDATE)" \
		--build-arg="DEBUG=$(DEBUG)" \
		--progress=plain \
		-f Dockerfile --target=validate .

.PHONY: binary
binary:
	@echo "INFO: Building K3s binaries and assets..."
	. ./scripts/git_version.sh && \
	docker buildx build \
		--build-arg "GIT_TAG=$$GIT_TAG" \
		--build-arg "TREE_STATE=$$TREE_STATE" \
		--build-arg "COMMIT=$$COMMIT" \
		--build-arg "DIRTY=$$DIRTY" \
		--build-arg="GOCOVER=$(GOCOVER)" \
		--build-arg="GOOS=$(GOOS)" \
		--build-arg="DEBUG=$(DEBUG)" \
		-f Dockerfile --target=result --output=. .

.PHONY: multiarch-binary
multiarch-binary:
	@echo "INFO: Building K3s binaries and assets for all release platforms..."
	. ./scripts/git_version.sh && \
	docker buildx build \
		--platform linux/amd64,linux/arm64,linux/arm/v7,linux/riscv64,windows/amd64 \
		--build-arg "GIT_TAG=$$GIT_TAG" \
		--build-arg "TREE_STATE=$$TREE_STATE" \
		--build-arg "COMMIT=$$COMMIT" \
		--build-arg "DIRTY=$$DIRTY" \
		--build-arg="GOCOVER=$(GOCOVER)" \
		--build-arg="DEBUG=$(DEBUG)" \
		-f Dockerfile --target=multiarch-result --output type=local,dest=.,platform-split=false .

.PHONY: image
image: binary
	@echo "INFO: Building K3s image..."
	./scripts/package-image

.PHONY: airgap
airgap: 
	@echo "INFO: Building K3s airgap tarball..."
	./scripts/package-airgap

.PHONY: ci
ci:  binary image airgap


# Closed native binary stages reuse the ordinary Dockerfile and its BuildKit cache.
K3S_BINARY_STAGE_TARGETS := binary-infra binary-deps-runc binary-deps-rootfs binary-deps-containerd binary-deps-charts binary-cni binary-server binary-shim binary-runc binary-package-prepare binary-package-compress binary-package-cli
binary-infra: K3S_BINARY_STAGE := infra
binary-deps-runc: K3S_BINARY_STAGE := download-runc
binary-deps-rootfs: K3S_BINARY_STAGE := download-rootfs
binary-deps-containerd: K3S_BINARY_STAGE := download-containerd
binary-deps-charts: K3S_BINARY_STAGE := manifests
binary-cni: K3S_BINARY_STAGE := build-cni
binary-server: K3S_BINARY_STAGE := build-server
binary-shim: K3S_BINARY_STAGE := build-shim
binary-runc: K3S_BINARY_STAGE := build-runc
binary-package-prepare: K3S_BINARY_STAGE := package-prepare
binary-package-compress: K3S_BINARY_STAGE := package-compress
binary-package-cli: K3S_BINARY_STAGE := build
.PHONY: $(K3S_BINARY_STAGE_TARGETS)
$(K3S_BINARY_STAGE_TARGETS):
	. ./scripts/git_version.sh && \
	docker buildx build --platform linux/amd64 $(KUBERNETES_TEST_RESOURCES) \
		--build-arg "GIT_TAG=$$GIT_TAG" --build-arg "TREE_STATE=$$TREE_STATE" \
		--build-arg "COMMIT=$$COMMIT" --build-arg "DIRTY=$$DIRTY" \
		--build-arg "GOCOVER=$(GOCOVER)" --build-arg "DEBUG=$(DEBUG)" \
		--progress=plain -f Dockerfile --target "$(K3S_BINARY_STAGE)" --output type=cacheonly .

.PHONY: binary-package-graph binary-cache-packages binary-export
binary-package-graph:
	mkdir -p dist/native-kubernetes-tests/binary-package-graph
	. ./scripts/git_version.sh && \
	docker buildx build --platform linux/amd64 $(KUBERNETES_TEST_RESOURCES) \
		--build-arg "GIT_TAG=$$GIT_TAG" --build-arg "TREE_STATE=$$TREE_STATE" \
		--build-arg "COMMIT=$$COMMIT" --build-arg "DIRTY=$$DIRTY" \
		--build-arg "GOCOVER=$(GOCOVER)" --build-arg "DEBUG=$(DEBUG)" \
		--progress=plain -f Dockerfile --target binary-package-graph-result \
		--output type=local,dest=dist/native-kubernetes-tests/binary-package-graph .

binary-cache-packages:
	test "$(words $(MAKECMDGOALS))" -eq 1
	[[ "$(K3S_BUILD_PACKAGE)" =~ ^[A-Za-z0-9_][A-Za-z0-9_./+-]*$$ ]]
	$(KUBERNETES_RUN_VALIDATE)
	. ./scripts/git_version.sh && \
	docker buildx build --platform linux/amd64 $(KUBERNETES_TEST_RESOURCES) \
		--build-arg "GIT_TAG=$$GIT_TAG" --build-arg "TREE_STATE=$$TREE_STATE" \
		--build-arg "COMMIT=$$COMMIT" --build-arg "DIRTY=$$DIRTY" \
		--build-arg "GOCOVER=$(GOCOVER)" --build-arg "DEBUG=$(DEBUG)" \
		--build-arg "K3S_BUILD_PACKAGE=$(K3S_BUILD_PACKAGE)" --build-arg "KUBERNETES_RUN_ID=$(KUBERNETES_RUN_ID)" \
		--progress=plain -f Dockerfile --target binary-package-cache --output type=cacheonly .

binary-export:
	. ./scripts/git_version.sh && \
	docker buildx build --platform linux/amd64 $(KUBERNETES_TEST_RESOURCES) \
		--build-arg "GIT_TAG=$$GIT_TAG" --build-arg "TREE_STATE=$$TREE_STATE" \
		--build-arg "COMMIT=$$COMMIT" --build-arg "DIRTY=$$DIRTY" \
		--build-arg "GOCOVER=$(GOCOVER)" --build-arg "DEBUG=$(DEBUG)" \
		--progress=plain -f Dockerfile --target result --output . .

# Native Kubernetes dependency checks use this consumer's selected Go graph.
KUBERNETES_ADMISSION_PACKAGE := k8s.io/kubernetes/pkg/kubelet/cm/admission
KUBERNETES_PLUGIN_PACKAGE := k8s.io/kubernetes/pkg/kubelet/cm/devicemanager/plugin/v1beta1
KUBERNETES_DEVICE_PACKAGE := k8s.io/kubernetes/pkg/kubelet/cm/devicemanager
KUBERNETES_ALLOCATION_PACKAGE := k8s.io/kubernetes/pkg/kubelet/allocation
KUBERNETES_KUBELET_PACKAGE := k8s.io/kubernetes/pkg/kubelet
KUBERNETES_CRONJOB_PACKAGE := k8s.io/kubernetes/pkg/controller/cronjob
KUBERNETES_IMAGES_PACKAGE := k8s.io/kubernetes/pkg/kubelet/images
KUBERNETES_TEST_PACKAGES := $(KUBERNETES_ADMISSION_PACKAGE) $(KUBERNETES_PLUGIN_PACKAGE) $(KUBERNETES_DEVICE_PACKAGE) $(KUBERNETES_ALLOCATION_PACKAGE) $(KUBERNETES_KUBELET_PACKAGE) $(KUBERNETES_CRONJOB_PACKAGE) $(KUBERNETES_IMAGES_PACKAGE)
KUBERNETES_TEST_MEMORY_BYTES := 12884901888
KUBERNETES_TEST_CPU_PERIOD := 100000
KUBERNETES_TEST_CPU_QUOTA := 400000
KUBERNETES_TEST_PLATFORM := linux/amd64
KUBERNETES_TEST_RESOURCES = --resource memory=$(KUBERNETES_TEST_MEMORY_BYTES) --resource memory-swap=$(KUBERNETES_TEST_MEMORY_BYTES) --resource cpu-period=$(KUBERNETES_TEST_CPU_PERIOD) --resource cpu-quota=$(KUBERNETES_TEST_CPU_QUOTA)
KUBERNETES_TEST_OUTPUT = dist/native-kubernetes-tests/$@
KUBERNETES_FOCUS_TARGETS := kubernetes-test-admission kubernetes-test-plugin kubernetes-test-device-manager kubernetes-test-allocation kubernetes-test-kubelet kubernetes-test-cronjob kubernetes-test-images


KUBERNETES_CACHE_TARGETS := kubernetes-cache-packages kubernetes-cache-state
KUBERNETES_TEST_GRAPH ?= false
KUBERNETES_OWNER_NAMES := admission plugin device-manager allocation kubelet cronjob images
KUBERNETES_COMPILE_TARGETS := $(addprefix kubernetes-test-compile-,$(KUBERNETES_OWNER_NAMES))
KUBERNETES_LIST_TARGETS := $(addprefix kubernetes-test-list-,$(KUBERNETES_OWNER_NAMES))
KUBERNETES_ASSEMBLED_TARGETS := $(addprefix kubernetes-test-assembled-,$(KUBERNETES_OWNER_NAMES))
.PHONY: kubernetes-module-download kubernetes-test-base $(KUBERNETES_CACHE_TARGETS) kubernetes-test-readiness $(KUBERNETES_COMPILE_TARGETS) $(KUBERNETES_LIST_TARGETS) $(KUBERNETES_FOCUS_TARGETS) $(KUBERNETES_ASSEMBLED_TARGETS) native-segments-check
native-segments-check:
	python3 scripts/test-build-segments.py

# Native Go package addresses come from its -deps/-test graph, never another selector store.
kubernetes-cache-packages: KUBERNETES_CACHE_STAGE := kubernetes-package-cache
kubernetes-cache-packages: KUBERNETES_CACHE_OUTPUT = type=cacheonly
kubernetes-cache-packages: KUBERNETES_CACHE_PREPARE = $(KUBERNETES_RUN_VALIDATE)
kubernetes-cache-packages: KUBERNETES_CACHE_FLAGS = --build-arg "KUBERNETES_RUN_ID=$(KUBERNETES_RUN_ID)"
# A supplied request identity changes fresh RUN input without IgnoreCache/cache resets.
KUBERNETES_RUN_VALIDATE = [[ "$(KUBERNETES_RUN_ID)" =~ ^[A-Za-z0-9_][A-Za-z0-9_.+-]*$$ ]]
kubernetes-cache-state: KUBERNETES_CACHE_STAGE := kubernetes-cache-state-result
kubernetes-cache-state: KUBERNETES_CACHE_OUTPUT = type=local,dest=$(KUBERNETES_TEST_OUTPUT)
kubernetes-cache-state: KUBERNETES_CACHE_PREPARE = [[ "$(KUBERNETES_TEST_GRAPH)" == false || "$(KUBERNETES_TEST_GRAPH)" == true ]] && $(KUBERNETES_RUN_VALIDATE) && mkdir -p "$(KUBERNETES_TEST_OUTPUT)"
kubernetes-cache-state: KUBERNETES_CACHE_FLAGS = --build-arg "KUBERNETES_RUN_ID=$(KUBERNETES_RUN_ID)" $(if $(filter true,$(KUBERNETES_TEST_GRAPH)),--build-arg "KUBERNETES_TEST_GRAPH=true") --metadata-file "$(KUBERNETES_TEST_OUTPUT)/buildx-metadata.json"
$(KUBERNETES_CACHE_TARGETS):
	test "$(words $(MAKECMDGOALS))" -eq 1
	[[ "$(KUBERNETES_BUILD_PACKAGE)" =~ ^[A-Za-z0-9_][A-Za-z0-9_./+-]*$$ ]]
	$(KUBERNETES_CACHE_PREPARE)
	docker buildx build --platform "$(KUBERNETES_TEST_PLATFORM)" $(KUBERNETES_TEST_RESOURCES) \
		--build-arg "KUBERNETES_BUILD_PACKAGE=$(KUBERNETES_BUILD_PACKAGE)" \
		$(KUBERNETES_CACHE_FLAGS) --progress=plain -f Dockerfile.test --target "$(KUBERNETES_CACHE_STAGE)" \
		--output "$(KUBERNETES_CACHE_OUTPUT)" .

kubernetes-module-download:
	test "$(words $(MAKECMDGOALS))" -eq 1
	[[ "$(KUBERNETES_DOWNLOAD_MODULE)" =~ ^[A-Za-z0-9_][A-Za-z0-9_./+-]*$$ && "$(KUBERNETES_DOWNLOAD_MODULE)" != all && "$(KUBERNETES_DOWNLOAD_MODULE)" != *...* ]]
	$(KUBERNETES_RUN_VALIDATE)
	mkdir -p "$(KUBERNETES_TEST_OUTPUT)"
	docker buildx build --platform "$(KUBERNETES_TEST_PLATFORM)" $(KUBERNETES_TEST_RESOURCES) \
		--build-arg "KUBERNETES_DOWNLOAD_MODULE=$(KUBERNETES_DOWNLOAD_MODULE)" --build-arg "KUBERNETES_RUN_ID=$(KUBERNETES_RUN_ID)" \
		--progress=plain --metadata-file "$(KUBERNETES_TEST_OUTPUT)/buildx-metadata.json" \
		-f Dockerfile.test --target kubernetes-module-download-result \
		--output "type=local,dest=$(KUBERNETES_TEST_OUTPUT)" .

kubernetes-test-base:
	docker buildx build --platform "$(KUBERNETES_TEST_PLATFORM)" $(KUBERNETES_TEST_RESOURCES) \
		--progress=plain -f Dockerfile.test --target kubernetes-test-base --output type=cacheonly .

kubernetes-test-readiness:
	$(KUBERNETES_RUN_VALIDATE)
	mkdir -p "$(KUBERNETES_TEST_OUTPUT)"
	docker buildx build --platform "$(KUBERNETES_TEST_PLATFORM)" $(KUBERNETES_TEST_RESOURCES) \
		--build-arg "KUBERNETES_TEST_PACKAGES=$(KUBERNETES_TEST_PACKAGES)" \
		--build-arg "KUBERNETES_TEST_MEMORY_BYTES=$(KUBERNETES_TEST_MEMORY_BYTES)" \
		--build-arg "KUBERNETES_TEST_CPU_PERIOD=$(KUBERNETES_TEST_CPU_PERIOD)" \
		--build-arg "KUBERNETES_TEST_CPU_QUOTA=$(KUBERNETES_TEST_CPU_QUOTA)" \
		--build-arg "KUBERNETES_RUN_ID=$(KUBERNETES_RUN_ID)" --progress=plain \
		--metadata-file "$(KUBERNETES_TEST_OUTPUT)/buildx-metadata.json" \
		-f Dockerfile.test --target kubernetes-test-readiness-result \
		--output "type=local,dest=$(KUBERNETES_TEST_OUTPUT)" .

kubernetes-test-admission kubernetes-test-compile-admission kubernetes-test-list-admission kubernetes-test-assembled-admission: KUBERNETES_TEST_PACKAGE := $(KUBERNETES_ADMISSION_PACKAGE)
kubernetes-test-plugin kubernetes-test-compile-plugin kubernetes-test-list-plugin kubernetes-test-assembled-plugin kubernetes-test-outline-plugin: KUBERNETES_TEST_PACKAGE := $(KUBERNETES_PLUGIN_PACKAGE)
kubernetes-test-device-manager kubernetes-test-compile-device-manager kubernetes-test-list-device-manager kubernetes-test-assembled-device-manager: KUBERNETES_TEST_PACKAGE := $(KUBERNETES_DEVICE_PACKAGE)
kubernetes-test-allocation kubernetes-test-compile-allocation kubernetes-test-list-allocation kubernetes-test-assembled-allocation: KUBERNETES_TEST_PACKAGE := $(KUBERNETES_ALLOCATION_PACKAGE)
kubernetes-test-kubelet kubernetes-test-compile-kubelet kubernetes-test-list-kubelet kubernetes-test-assembled-kubelet: KUBERNETES_TEST_PACKAGE := $(KUBERNETES_KUBELET_PACKAGE)
kubernetes-test-cronjob kubernetes-test-compile-cronjob kubernetes-test-list-cronjob kubernetes-test-assembled-cronjob: KUBERNETES_TEST_PACKAGE := $(KUBERNETES_CRONJOB_PACKAGE)
kubernetes-test-images kubernetes-test-compile-images kubernetes-test-list-images kubernetes-test-assembled-images: KUBERNETES_TEST_PACKAGE := $(KUBERNETES_IMAGES_PACKAGE)
kubernetes-test-admission kubernetes-test-plugin kubernetes-test-outline-plugin: KUBERNETES_TEST_RUN := Test
kubernetes-test-device-manager: KUBERNETES_TEST_RUN := TestDeviceInventory|TestDevicesToAllocate|TestCheckpoint
kubernetes-test-allocation: KUBERNETES_TEST_RUN := TestDeferredAdmission|TestAddPod|TestCanAdmitPod
kubernetes-test-kubelet: KUBERNETES_TEST_RUN := TestDeferredAdmission|TestKubelet_HandlePodCleanups|TestHandlePodCleanups|TestHandlePluginResources
kubernetes-test-cronjob: KUBERNETES_TEST_RUN := TestDeleteJob|TestRealJobControlDelete
kubernetes-test-images: KUBERNETES_TEST_RUN := ^(TestDetectImagesContainerDisappearsBetweenListAndStatus|TestDetectImagesContainerStatusErrorsRemainFailures|TestDetectImagesImageVolumeDisabledDoesNotQueryStatus)$$
$(KUBERNETES_ASSEMBLED_TARGETS): KUBERNETES_TEST_RUN := .

$(KUBERNETES_COMPILE_TARGETS): KUBERNETES_CONSTRUCTION_STAGE := kubernetes-test-compile-result
$(KUBERNETES_LIST_TARGETS): KUBERNETES_CONSTRUCTION_STAGE := kubernetes-test-list-result
$(KUBERNETES_COMPILE_TARGETS) $(KUBERNETES_LIST_TARGETS):
	mkdir -p "$(KUBERNETES_TEST_OUTPUT)"
	docker buildx build --platform "$(KUBERNETES_TEST_PLATFORM)" $(KUBERNETES_TEST_RESOURCES) \
		--build-arg "KUBERNETES_TEST_PACKAGES=$(KUBERNETES_TEST_PACKAGES)" \
		--build-arg "KUBERNETES_TEST_PACKAGE=$(KUBERNETES_TEST_PACKAGE)" \
		--progress=plain --metadata-file "$(KUBERNETES_TEST_OUTPUT)/buildx-metadata.json" \
		-f Dockerfile.test --target "$(KUBERNETES_CONSTRUCTION_STAGE)" \
		--output "type=local,dest=$(KUBERNETES_TEST_OUTPUT)" .

# One native Make command owns the selected test inputs for execution and outline.
KUBERNETES_TEST_BUILD = docker buildx build --platform "$(KUBERNETES_TEST_PLATFORM)" $(KUBERNETES_TEST_RESOURCES) \
    --build-arg "KUBERNETES_TEST_PACKAGES=$(KUBERNETES_TEST_PACKAGES)" \
    --build-arg "KUBERNETES_TEST_PACKAGE=$(KUBERNETES_TEST_PACKAGE)" \
    --build-arg "KUBERNETES_TEST_RUN=$(KUBERNETES_TEST_RUN)" \
    --build-arg "KUBERNETES_RUN_ID=$(KUBERNETES_RUN_ID)" --progress=plain \
    -f Dockerfile.test --target kubernetes-test-result

$(KUBERNETES_FOCUS_TARGETS) $(KUBERNETES_ASSEMBLED_TARGETS):
	$(KUBERNETES_RUN_VALIDATE)
	mkdir -p "$(KUBERNETES_TEST_OUTPUT)"
	$(KUBERNETES_TEST_BUILD) \
		--metadata-file "$(KUBERNETES_TEST_OUTPUT)/buildx-metadata.json" \
		--output "type=local,dest=$(KUBERNETES_TEST_OUTPUT)" .

.PHONY: kubernetes-test-outline-plugin
kubernetes-test-outline-plugin:
	test "$(words $(MAKECMDGOALS))" -eq 1
	$(KUBERNETES_RUN_VALIDATE)
	$(KUBERNETES_TEST_BUILD) --call=outline .
