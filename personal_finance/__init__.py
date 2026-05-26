"""Personal Finance ledger — 雙式記賬，但用個人化嘅 chart of accounts。

設計理念：
- 用會計入面真正嘅 double-entry，每筆都係 Dr / Cr 平衡
- Account 分 4 種：asset (現金/銀行)、liability (信用卡未還)、
                    expense (餐飲/交通等 14 個)、income (人工/紅利)
- Invoice 提取後自動 post entry：Dr 餐飲 / Cr Visa
- 月度 budget 設限額，超支警告
- Project（旅行、裝修）獨立追蹤
"""
