# 输入与恢复契约

- 输入支持 UTF-8/UTF-8 BOM 的 `.csv` 或每行一个 JSON 对象的 `.jsonl`。
- 模板使用 `{column_name}` 占位符；字段名仅支持字母、数字和下划线。
- 输出增加 `_batch_row`、`ai_status`、`ai_error` 和指定的结果列。
- `--resume` 只跳过同一输出文件中 `ai_status=ok` 的行号。输入顺序改变后不要复用旧输出。
- CSV 需要唯一表头。二进制 Excel 文件先另存为 CSV，避免公式、宏和隐藏列被误处理。
