import { useCallback, useMemo, useRef, useState } from "react";
import { Form, Input, Select, Tag, Tooltip } from "antd";
import type { FormInstance } from "antd/es/form";

export type HistoryStringFilterKey =
  | "start_time"
  | "subtask"
  | "case_name"
  | "main_module"
  | "case_result"
  | "case_level"
  | "platform"
  | "code_branch"
  | "failure_owner"
  | "failed_type";

function containsFieldName(name: HistoryStringFilterKey): string {
  return `${name}_contains`;
}

export interface HistoryStringMultiFilterProps {
  name: HistoryStringFilterKey;
  label: string;
  options: { label: string; value: string }[];
  loading?: boolean;
  /** 与外层 Form `disabled` 一致，用于禁用子串 Tag 关闭等 */
  disabled?: boolean;
  /** 无子串、无多选时的占位说明 */
  placeholder?: string;
  form: FormInstance;
}

/**
 * 执行历史页字符串多选筛选项：支持搜索、下拉首行「全部」（有匹配候选项且搜索非空时展示）、
 * 与隐藏字段 `name_contains` 同步；选具体项或清空时清除子串条件。
 */
export function HistoryStringMultiFilter(props: HistoryStringMultiFilterProps) {
  const { name, label, options, loading, disabled, placeholder, form } = props;
  const cname = containsFieldName(name);
  const [searchText, setSearchText] = useState("");
  const suppressNextEmptyChangeRef = useRef(false);

  const containsVal = Form.useWatch(cname, form) as string | undefined;
  const trimContains = useMemo(() => {
    const t = containsVal != null ? String(containsVal).trim() : "";
    return t || undefined;
  }, [containsVal]);

  const filtered = useMemo(() => {
    const q = searchText.trim().toLowerCase();
    if (!q) return options;
    return options.filter((o) => (o.label ?? "").toString().toLowerCase().includes(q));
  }, [options, searchText]);

  const showAllRow = filtered.length > 0 && searchText.trim() !== "";

  const onSelectAllMatched = useCallback(() => {
    const kw = searchText.trim();
    if (!kw) return;
    suppressNextEmptyChangeRef.current = true;
    form.setFieldsValue({
      [name]: undefined,
      [cname]: kw,
    });
    setSearchText("");
  }, [cname, form, name, searchText]);

  const onSelectChange = useCallback(
    (vals: string[] | undefined) => {
      if (vals?.length) {
        suppressNextEmptyChangeRef.current = false;
        form.setFieldsValue({ [cname]: undefined });
        return;
      }
      if (suppressNextEmptyChangeRef.current) {
        suppressNextEmptyChangeRef.current = false;
        return;
      }
      form.setFieldsValue({ [cname]: undefined });
    },
    [cname, form]
  );

  return (
    <>
      <Form.Item name={cname} hidden>
        <Input />
      </Form.Item>
      <Form.Item label={label} style={{ marginBottom: 8 }}>
        <div className="history-filter-string-multi">
          {trimContains ? (
            <Tooltip title={trimContains}>
              <Tag
                bordered={false}
                closable={!disabled}
                className="history-filter-substring-tag"
                onClose={(e) => {
                  e.preventDefault();
                  form.setFieldsValue({ [cname]: undefined });
                }}
              >
                子串 {trimContains}
              </Tag>
            </Tooltip>
          ) : null}
          <Form.Item name={name} noStyle>
            <Select
              mode="multiple"
              variant="borderless"
              className="history-filter-combined-select"
              allowClear
              placeholder={placeholder ?? "全部"}
              maxTagCount="responsive"
              loading={loading}
              showSearch
              searchValue={searchText}
              onSearch={setSearchText}
              onChange={onSelectChange}
              onClear={() => {
                suppressNextEmptyChangeRef.current = false;
                form.setFieldsValue({ [cname]: undefined });
              }}
              autoClearSearchValue={false}
              filterOption={(input, option) =>
                (option?.label ?? "").toString().toLowerCase().includes(input.toLowerCase())
              }
              options={options}
              dropdownRender={(menu) => (
                <div>
                  {showAllRow ? (
                    <div
                      role="button"
                      tabIndex={0}
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={onSelectAllMatched}
                      style={{
                        padding: "8px 12px",
                        cursor: "pointer",
                        borderBottom: "1px solid #f0f0f0",
                      }}
                    >
                      全部
                    </div>
                  ) : null}
                  {menu}
                </div>
              )}
            />
          </Form.Item>
        </div>
      </Form.Item>
    </>
  );
}
