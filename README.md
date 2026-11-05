# Macro Lens｜總體經濟觀測站

台灣與美國經濟指標、互動利率及外匯圖表，以及原生可編輯 PowerPoint 報告工作站。

## 使用

- 經濟總覽：台灣GDP、CPI、工業生產、進出口、外銷訂單、就業、存底；近12個月景氣燈號；美國2年/10年公債、CPI、非農、實質GDP。
- 利率：台灣政策利率、隔夜拆款、3個月TAIBOR、10年公債；美債期限利差。
- 外匯：USD/TWD、USD/JPY、TWD/JPY與Fed廣義美元指數（非DXY）。
- 報告製作：勾選圖表、設定期間、拖曳排序、16:9預覽、單圖PNG及原生可編輯PPTX。一頁一張圖；不增加封面。選擇保存在瀏覽器localStorage，無個人資料後端。
- FedWatch僅連結CME官方工具，不抓取或公開轉載其機率。

## 每日更新及發布

`.github/workflows/daily-update.yml` 於每日 **13:30 UTC / 21:30 Asia/Taipei**、main推送或手動觸發。

流程：取得官方資料 → 驗證日期/數值/12個月燈號/交叉匯率 → 保存資料與檢查狀態 → 公開網站讀取更新資料。頁面無需開啟。GitHub排程非準時SLA，可能延遲。每日有資料檢查紀錄commit。

個別來源失敗不清空最後有效值，頁面ⓘ顯示來源錯誤與各序列最後成功檢查時間。超過36小時沒有執行紀錄，狀態視窗顯示提醒。禁止以假數據或插值填補缺失。

## 資料定義與目前涵蓋範圍

|來源|指標|頻率/注意事項|
|---|---|---|
|主計總處Point圖表及最新新聞稿Excel|CPI/核心/季調月增、失業/季調失業/勞參、CPI七大分類|月；分類隨最新發布稿更新；保留修正數據|
|經濟部首頁（原始為主計總處）|台灣GDP年增率|季；初次包含首頁可取得的近期季度，之後累積；未捏造長期歷史|
|經濟部d.csv/b.csv|工業/製造業生產、外銷訂單|月；年增率由官方歷史原始數值計算，四捨五入可能與公告一位小數有差異|
|財政部開放CSV|進出口及順差|月；出口FOB，進口CIF；百萬美元轉億美元|
|國發會6099 ZIP|景氣燈號及領先指標|月；燈號9–45分；首頁連續最近12個已公布月|
|央行API/CSV/表格|USD/TWD、存底、重貼現、拆款、台灣10年期公債|匯率日；存底及公債月；政策按生效日期；拆款初次近20日後累積|
|銀行公會TAIBOR每日ZIP|3個月TAIBOR|初次近40個營業日後累積|
|美國財政部XML|2/10年Par Yield Curve及期限利差|日；美國當日收盤通常要台灣隔日檢查才能取得|
|BLS公開API|美國CPI/核心及非農|月；CPI年增採未季調指數；非農採季調千人，月增由相鄰月份計算並包含修正|
|BEA/Fed官方發布頁（初始歷史含FRED）|美國實質GDP、USD/JPY、廣義美元指數、政策上限|GDP季增年率；Fed H.10日觀測按週公布；非DXY、非盤中報價|
|TWSE OpenAPI|加權指數|官方最新月份；之後每日累積|

TWD/JPY = USD/JPY ÷ USD/TWD。僅用同日資料計算，但兩個來源報價時點不同，為參考交叉匯率，非交易報價。美國GDP季增年率不可直接與台灣GDP年增率比較。

每序列保存來源URL、單位、頻率、資料期間、最後成功檢查時間及取得到的官方發布日期；未提供發布日期者明示未提供，絕不以抓取時間代替。

新聞僅使用官方標題、日期與原文連結，不自動生成原因或投資結論。日曆僅列可從官方頁面辨識的明確預告日期，另提供台灣官方發布日曆入口。

## 本機維護

```sh
pip install -r requirements.txt
npm ci --ignore-scripts
npm run build
python scripts/update_data.py
npm test
python -m http.server 8000 --directory dist
```

前端為原生HTML/CSS/JS。ECharts 5.6.0與PptxGenJS 4.0.1由lockfile鎖定，部署時複製至本地vendor並附授權文字。PPTX使用原生OOXML圖表與內嵌工作簿，並非圖表截圖。未使用API密鑰、AI付費服務、商用市場報價或附件報告原文。

公開網站：https://macro-lens-taiwan.selina84823.chatgpt.site

網站由Sites承載；程式及每日資料更新保存在本GitHub儲存庫。網站開啟時讀取main分支的最新資料，連線失敗時退回網站內保存的資料並提示。GitHub Pages未啟用，不影響目前網址與每日更新。

配色依指定瑞穗參考頁：#285AE1 / #08287F / #F0F4FF / #C0D2FF / #FFFFFF / #333333 / #D92214。景氣燈號保留官方五色。

## 語言與黑白輸出

網站頂部 `Language: CH / EN / JP` 切換繁體中文、英文、日文，並記住本機設定。可分享 `?lang=CH`、`?lang=EN` 或 `?lang=JP` 連結。圖表標題、軸與圖例、來源註記、CSV、PNG與PPTX均依目前語言輸出。切換語言不會改變原始數值、單位倍率、選擇、期間或排序。

報告頁的「黑白 / Black & white / 白黒」套用整份簡報、預覽及該頁單圖下載。黑白PPT使用原生灰階圖表、文字與圖形；不透過圖片截圖轉換，資料表仍可編輯。多系列另使用線型區分。

新聞的現有標題附人工英日譯文；未收錄的新標題顯示當地語言的來源與日期標籤並連回原文，不憑空產生新聞內容。每張數據圖表與介面元件皆使用同一份翻譯目錄。

`npm test` 驗證資料完整性，並實際產生三語×彩色／黑白六份含全部22張原生圖表的PPTX，檢查132個圖表及內嵌工作簿、英文標題無中文殘留，以及黑白輸出無非灰階繪圖色。測試檔案在暫存目錄建立，結束即清除。

GDP charts default to the last 10 years (quarterly), with a 10-year period option shared by chart details and PPT exports. Taiwan history is refreshed directly from DGBAS’s economic growth chart; dates denote quarter starts and published revisions replace prior values. US BEA/FRED quarterly history is backfilled from 2015.
