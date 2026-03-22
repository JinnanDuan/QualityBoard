/**
 * 用例执行历史钻取页 — 规约 spec/12_history_case_drilldown_spec.md
 * 与详细执行历史共用表格与接口，默认不带批次（全时间范围，见 Spec 08 §3.1.1）。
 */
import HistoryPage from "./HistoryPage";

export default function CaseExecutionsHistoryPage() {
  return <HistoryPage drilldown />;
}
