# Test Templates

This directory stores non-production workflow template fixtures for manual QA and prompt tuning.

## Files

- `测试广告数据.xlsx`
  - Shared spreadsheet fixture for Amazon ads analysis templates.
  - `WorkflowTemplateSampleService` uses this file as `fileUrl` (`file://...`) for ads-related templates with `input_file` nodes.

- `测试Listing数据.xlsx`
  - Shared spreadsheet fixture for Amazon listing optimization templates.
  - Default columns: `标题`, `五点`, `产品描述`, `排名`.
  - Auto-created by `backend/materialize_template_samples.py` when missing.
  - `WorkflowTemplateSampleService` injects this file as `fileUrl` for listing optimization templates.

- `测试数据分析数据.xlsx`
  - Shared spreadsheet fixture for data-analysis templates.
  - Auto-created by `backend/materialize_template_samples.py` when missing.
  - Data-analysis template sample rendering uses this file before execution and runs non-workflow analysis materialization.

- `listing_optimization_keyword_matrix_v1.json`
- `listing_optimization_review_gap_v1.json`
- `listing_optimization_compliance_localization_v1.json`
  - Listing-optimization template variants for local testing.
  - They are fixtures and are not auto-seeded into starter templates.
