-- 样例数据：pipeline_overview（从 pipeline_history 聚合生成）
-- 关联 seed_pipeline_history，按 (batch, subtask, platform, code_branch) 聚合
-- 可重复执行（先清空全表再插入）
-- 执行顺序：需在 seed_pipeline_history.sql 之后执行

DELETE FROM `pipeline_overview`;

INSERT INTO `pipeline_overview`
  (`batch`, `subtask`, `result`, `case_num`, `batch_start`, `batch_end`, `reports_url`, `log_url`, `screenshot_url`, `pipeline_url`, `passed_num`, `failed_num`, `platform`, `code_branch`)
SELECT
  ph.start_time AS batch,
  ph.subtask,
  CASE WHEN SUM(CASE WHEN ph.case_result = 'failed' THEN 1 ELSE 0 END) > 0 THEN 'failed' ELSE 'passed' END AS result,
  CAST(COUNT(*) AS CHAR) AS case_num,
  STR_TO_DATE(ph.start_time, '%Y%m%d%H%i') AS batch_start,
  DATE_ADD(STR_TO_DATE(ph.start_time, '%Y%m%d%H%i'), INTERVAL 15 MINUTE) AS batch_end,
  'www.baidu.com' AS reports_url,
  'www.sohu.com' AS log_url,
  'www.sina.com' AS screenshot_url,
  'www.tencent.com' AS pipeline_url,
  SUM(CASE WHEN ph.case_result = 'passed' THEN 1 ELSE 0 END) AS passed_num,
  SUM(CASE WHEN ph.case_result = 'failed' THEN 1 ELSE 0 END) AS failed_num,
  ph.platform,
  ph.code_branch
FROM pipeline_history ph
GROUP BY ph.start_time, ph.subtask, ph.platform, ph.code_branch;
