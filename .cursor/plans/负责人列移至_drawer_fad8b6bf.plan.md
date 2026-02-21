---
name: 负责人列移至 Drawer
overview: 将详细执行历史表格中的「负责人」列从表格中移除，改为在 Drawer 的基本信息区以「用例开发责任人」展示；同时移除负责人相关的筛选与排序能力。
todos: []
isProject: false
---

# 负责人列移至 Drawer 基本信息区

## 变更要点

- 表格中移除「负责人」列
- Drawer 基本信息区新增「用例开发责任人」（展示 `owner` 字段）
- **不再支持**按负责人筛选、排序（前后端均移除）

---

## 修改范围

### 1. 前端：[frontend/src/pages/history/HistoryPage.tsx](frontend/src/pages/history/HistoryPage.tsx)

**1.1 移除表格中的负责人列**

删除 `columns` 数组中「负责人」列定义（约 427–439 行）。

**1.2 从 DEFAULT_WIDTHS 移除 owner**

在 `DEFAULT_WIDTHS`（约 126–139 行）中删除 `owner: 80`。

**1.3 移除筛选表单中的负责人筛选项**

删除 `Form.Item name="owner" label="负责人"` 及其内部 `Select`（约 654–671 行）。

**1.4 移除 URL 与请求参数中的 owner**

- `paramsFromUrl()`：删除 `owner: getList("owner")`
- `syncParamsToUrl()`：删除 `appendList("owner", params.owner)`
- `handleFilterChange` 中构建 query 时：删除 `owner` 字段
- `handleReset` 中 `setFieldsValue`：删除 `owner` 相关
- `Form` 的 `initialValues`：删除 `owner`

**1.5 在 Drawer 基本信息区新增用例开发责任人**

在「用例级别」与「平台」之间插入：

```tsx
<div style={{ marginBottom: 8 }}>
  <Text strong>用例开发责任人：</Text>
  {drawerRecord.owner ?? "—"}
</div>
```

---

### 2. 前端：[frontend/src/services/index.ts](frontend/src/services/index.ts)

- `HistoryQueryParams`：删除 `owner?: string[]`
- `HistoryFilterOptions`：删除 `owner: string[]`
- `toSearchParams()`：删除 `appendList("owner", params.owner)`

---

### 3. 后端：[backend/api/v1/history.py](backend/api/v1/history.py)

- 删除 `owner: Optional[List[str]] = Query(None)` 参数
- 删除 `HistoryQuery` 构造时的 `owner=owner`

---

### 4. 后端：[backend/schemas/history.py](backend/schemas/history.py)

- `HistoryQuery`：删除 `owner: Optional[List[str]] = None`
- `HistoryFilterOptions`：删除 `owner: List[str] = []`

**注意**：`HistoryItem` 中的 `owner` 字段保留（Drawer 展示用）。

---

### 5. 后端：[backend/services/history_service.py](backend/services/history_service.py)

- `list_history()`：删除 `if query.owner: stmt = stmt.where(PipelineHistory.owner.in_(query.owner))`
- `list_history()`：从 `allowed_sort_fields` 中删除 `"owner"`
- `get_history_options()`：删除 `owner = await _distinct(PipelineHistory.owner)` 及返回中的 `owner=owner`

---

### 6. 规格文档：[spec/02_history_fields_spec.md](spec/02_history_fields_spec.md)

- **1. 直接展示字段（表格列）**：删除 owner 所在行
- **2.1 基本信息区**：在 case_level 与 platform 之间新增 `owner | 用例开发责任人 | 纯文本`；删除说明「owner 在表格列中直接展示」，改为「owner 在 Drawer 基本信息区展示，名称为用例开发责任人」
- **3. 筛选字段清单**：删除 owner 所在行
- **4. 字段复用说明**：将 owner 行改为 `— | ✓ 基本信息 | —`（不再支持表格列、筛选）

---

## 保持不变

- `HistoryItem` / `HistoryItem` Schema 中的 `owner` 字段保留（单条记录数据，Drawer 展示）
- 数据库 `pipeline_history.owner` 列不变
