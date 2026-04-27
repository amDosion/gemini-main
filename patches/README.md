# patches/

第三方依赖的补丁。每次 `npm install` 后**必须**重新应用,否则补丁会被覆盖。

## 当前补丁

### `@reactflow+core+11.11.4.patch`

**问题**: ReactFlow 11.11.4 的 `useNodeOrEdgeTypes` 内部判断逻辑反了:

```js
// node_modules/@reactflow/core/dist/esm/index.js:3741(原版,有 bug)
if (shallow(typesKeysRef.current, typeKeys)) {
  store.getState().onError?.('002', errorMessages['error002']());
}
```

意图是"keys 集合变化时报警";实际写成了"keys 集合**相等**时报警"(条件反转)。
React 19 dev StrictMode 双 mount 下,第二次 mount 看到同一组 keys → `shallow=true`
→ **误触发 002 警告**。即使把 nodeTypes/edgeTypes 写成 module-level 常量也无法绕开。

**修复**: 反转条件 + 跳过首次 mount:

```js
if (!shallow(typesKeysRef.current, typeKeys) && typesKeysRef.current !== null) {
  store.getState().onError?.('002', errorMessages['error002']());
}
```

也对应同步 patch 了 vite 预捆绑缓存 `node_modules/.vite/deps/reactflow.js`(同一行),
避免清缓存才生效。

**长期方案**: 升级到 ReactFlow 12+(`@xyflow/react`)。需要 import 路径重命名 +
breaking change 验证。已记录到 Sprint 4 待办。

## 应用方式

### 推荐:patch-package(自动)

```bash
npm install --save-dev patch-package postinstall-postinstall
# 在 package.json 加: "scripts": { "postinstall": "patch-package" }
```

### 手动应用

```bash
cd /path/to/gemini-main
patch -p1 < patches/@reactflow+core+11.11.4.patch
```

vite 缓存同步:对 `node_modules/.vite/deps/reactflow.js` 第 7037 行做同语义反转;
或清空 `node_modules/.vite/` 让 vite 重新预捆绑(首次启动会慢约 30s)。
