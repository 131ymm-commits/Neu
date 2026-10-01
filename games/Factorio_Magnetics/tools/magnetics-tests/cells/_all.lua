-- все модули ячеек (порядок = порядок участков лаборатории)
-- tools/tests.py выносит модули ремонтной катушки (mend и любые cells/mend_*.lua) в отдельный прогон; файлы
-- cells/mend_*.lua он подхватывает сам, даже если их забыли вписать сюда (ревью c21)
return { "smoke", "static", "production", "logistics", "power", "quality", "combat", "mend" }
