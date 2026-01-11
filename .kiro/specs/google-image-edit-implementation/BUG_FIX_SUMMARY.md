# Bug Fix Summary: UnifiedProviderClient.editImage() Interface Mismatch

**Date**: 2026-01-11  
**Status**: 🐛 Bug Identified - Awaiting Fix  
**Severity**: High (TypeScript compilation error)  
**Spec**: google-image-edit-implementation  
**Task**: 10.1

---

## Problem Description

The `UnifiedProviderClient.editImage()` method has a **parameter mismatch** with the `ILLMProvider` interface:

- **Interface expects**: 5 parameters (no `apiKey`)
- **Implementation has**: 6 parameters (includes `apiKey`)

This causes a TypeScript compilation error:

```
类型"UnifiedProviderClient"中的属性"editImage"不可分配给基类型"ILLMProvider"中的同一属性。
不能将类型"(modelId: string, prompt: string, referenceImages: Attachment[], options: ChatOptions, apiKey: string, baseUrl: string) => Promise<ImageGenerationResult[]>"
分配给类型"(modelId: string, prompt: string, referenceImages: Attachment[], options: ChatOptions, baseUrl: string) => Promise<ImageGenerationResult[]>"。
目标签名提供的自变量太少。预期为 6 个或更多，但实际为 5 个。
```

---

## Root Cause

During Task 10 implementation, the `editImage()` method was incorrectly given an `apiKey` parameter, which violates the security design specified in **Requirement 7**:

> **Requirement 7**: 作为前端开发者，我希望通过 UnifiedProviderClient 调用图像编辑 API，这样保持接口一致性。
> 
> **Acceptance Criteria 2**: WHEN 发送请求，THEN THE System SHALL 不包含 apiKey 参数（安全性）

The `ILLMProvider` interface comment clearly states:
```typescript
// API Key is now managed by backend for UnifiedProviderClient
// Other providers may still require apiKey parameter
```

---

## Expected Behavior

The `editImage()` method should:
1. **NOT** accept an `apiKey` parameter
2. Use session-based authentication (cookies + JWT)
3. Match the `ILLMProvider` interface signature exactly

---

## Solution

### File to Modify
`frontend/services/providers/UnifiedProviderClient.ts`

### Changes Required

**Current (incorrect) signature:**
```typescript
async editImage(
  modelId: string,
  prompt: string,
  referenceImages: Record<string, any>,
  options: ChatOptions,
  apiKey: string,  // ❌ Remove this parameter
  baseUrl: string
): Promise<ImageGenerationResult[]>
```

**Correct signature:**
```typescript
async editImage(
  modelId: string,
  prompt: string,
  referenceImages: Record<string, any>,
  options: ChatOptions,
  baseUrl: string  // ✅ No apiKey parameter
): Promise<ImageGenerationResult[]>
```

### Implementation Notes

1. Remove the `apiKey` parameter from the method signature
2. Ensure the method body does NOT use `apiKey` anywhere
3. Verify that authentication is handled via:
   - `credentials: 'include'` (session cookies)
   - `Authorization` header (JWT token from auth context)
4. Run TypeScript compiler to verify no errors

---

## Verification Steps

After fixing:

1. ✅ TypeScript compilation succeeds (no errors)
2. ✅ `UnifiedProviderClient` implements `ILLMProvider` correctly
3. ✅ No `apiKey` is passed in the request body
4. ✅ Authentication works via session cookies and JWT
5. ✅ Manual test: Call `editImage()` and verify backend receives request

---

## Related Requirements

- **Requirement 1**: 后端图像编辑 API (安全性)
- **Requirement 7**: 前端集成 (不传递 API Key)

---

## Task Reference

**Task 10.1**: 修复 UnifiedProviderClient.editImage() 接口不匹配

See: `.kiro/specs/google-image-edit-implementation/tasks.md`

---

## Impact

- **Severity**: High (blocks TypeScript compilation)
- **Scope**: Frontend only
- **Risk**: Low (simple parameter removal)
- **Testing**: TypeScript compiler + manual API test

---

**Created**: 2026-01-11  
**Author**: Kiro AI Spec Agent
