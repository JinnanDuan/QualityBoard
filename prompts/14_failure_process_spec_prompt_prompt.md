现在要开发失败记录标注功能，请生成用于生成spec的prompt，注意不是直接生成spec，更不要直接开始写代码

关键要点如下：
1、针对详细执行历史页面的任意条执行记录进行标注处理
2、支持执行记录多选或者单选或者全选
3、找一个合适的地方放按钮，按钮名叫处理
4、点击按钮后出现对话框
5、对话框至少提供一下几部分：
    5.1 选择失败类型，选项来自case_failed_type.failed_reason_type
    5.2 自动分配个默认跟踪人，跟踪人来自对应的case_failed_type.owner，并且支持下拉自定义更改，备选数据来自于ums_email.employee_id
    5.3 给一个详细原因填入文本框
    5.4 以上都为必选
    5.5 如果失败类型选择为‘bug’，要多一个模块选项，默认给到该失败用例所属主模块，并且支持下拉自定义更改，备选数据来自于ums_module_owner.module，然后默认跟踪人给到对应的ums_module_owner.owner字段
6、对话框提供确定or取消按钮
7、如果取消，对话框消失，什么都不做
8、如果确定，进行数据变更，要变更以下几个数据
    8.1 pipeline_history.analyzed
    8.2 pipeline_failure_reason.owner 数据来自上面对话框最后选定的owner（注意匹配关系：case_name failed_batch platform）
    8.3 pipeline_failure_reason.reason 数据来自上面对话框最后填入的详细原因（注意匹配关系：case_name failed_batch platform）
    8.4 pipeline_failure_reason.failed_type 数据来自上面对话框最后选定的失败类型（注意匹配关系：case_name failed_batch platform）