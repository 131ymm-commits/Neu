Свод правил: автоматические заводы в FLE

Старт и архитектура
1. Проверь стартовый инвентарь. Если есть электробуры, электропечи и AM2, делай весь завод электрическим: топливо нужно только котлу. Burner-цепочки без агента встают. [L3p1:iron_plate_throughput, L3p2:все задачи; лечит: остановку после ухода агента]
2. Сразу запиши координаты ресурсов и воды. nearest() ищет от текущей позиции игрока, поэтому после move_to он может найти другое озеро. Осмотр ресурсов совмещай с первой стройкой. [L3p2:automation_science_pack_throughput, L3p2:iron_gear_wheel_throughput; лечит: трубы на 75 тайлов и потерянные шаги]

Энергия
3. Электростанция: offshore pump → boiler → steam engine. Котёл и двигатель ставь через nearest_buildable с BuildingBox. Насос и котёл соединяй через connect_entities(Pipe), это работает и на 30+ тайлах. Следующий двигатель ставь через place_entity_next_to(spacing=0), пар он подхватит сам. [L3p1, L3p2:iron_plate_throughput, L3p2:iron_gear_wheel_throughput; лечит: неудачную раскладку станции]
4. Лучший способ подать уголь: котёл прямо в drop_position электробура, через place_entity_next_to(Boiler, drill.position, UP). Можно поставить бур с двух сторон. Котёл держит 50 угля. Запасной вариант: бур → лента по одному тайлу → burner-инсертер. Проверь, что последний тайл ленты на месте: range() часто недотягивает на один тайл. [L3p2:iron_gear_wheel_throughput, L3p2:automation_science_pack_throughput, L3p2:logistics_science_pack_throughput; лечит: голодание котла]
5. Считай мощность так, будто все машины работают одновременно. 2 двигателя дают 1.8 МВт; бур берёт 90 кВт, печь 180 кВт, AM2 150 кВт. Если выходит больше, ставь второй котёл (вода через одну трубу со свободного порта первого) и 4 двигателя цепочкой. Для крафта двигателей вручную шестерни не делаются: достань их из AM2 через extract_item, а плиты возьми из печей. [L3p2:inserter_throughput, L3p2:logistics_science_pack_throughput; лечит: LOW_POWER]

Производство
6. В этой версии электропечь занимает 3x3. Ставь её в drop_position бура через place_entity_next_to(drill.position, UP), затем инсертер через place_entity_next_to(furnace.position, UP). Шаг колонки 3 тайла. На одну печь можно направить два бура навстречу. Пара бур+печь даёт ~30 плит/мин. Размеры проверяй через tile_dimensions. [L3p2:electronic_circuit_throughput, L3p2:logistics_science_pack_throughput, L3p2:iron_plate_throughput; лечит: машины впритык без места для инсертера]
7. Детали между машинами (печь → AM2 → AM2) передавай прямой вставкой. Обычный инсертер переносит ~0.83 предмета/с, поэтому на потоках больше этого ставь 2 инсертера параллельно. На одной ленте держи один тип предмета; разные ленты прокладывай по разные стороны ряда ассемблеров. [L3p1, L3p2:electronic_circuit_throughput, L3p2:logistics_science_pack_throughput; лечит: заторы и узкие места]
8. Закладывай запас 30% и больше: реальный выпуск ниже теоретического. Узкое место (одна печь, один инсертер) удваивай. [L3p1, L3p2:automation_science_pack_throughput; лечит: недобор квоты]
9. Выходной сундук заполняется быстро. Соедини через инсертеры 2–4 сундука. [L3p2:inserter_throughput, L3p2:iron_gear_wheel_throughput; лечит: выпуск 0 на долгом прогоне]

Стройка
10. Ставь не дальше 10 тайлов от игрока. Переменная позиции игрока устаревает, поэтому в циклах вызывай move_to каждые несколько тайлов. Вдали от игрока can_place_entity возвращает False, так что для разведки он не годится. Лучше place_entity в try/except с проверкой через get_entity. [L3p2:automation_science_pack_throughput, L3p2:logistics_science_pack_throughput, L3p2:electronic_circuit_throughput; лечит: отказы стройки]
11. place_entity может вернуть устаревший объект. Строй по явным координатам и перечитывай сущность через get_entity. Печатай pickup_position и drop_position инсертеров и при ошибке вызывай rotate_entity. [L3p1, L3p2:logistics_science_pack_throughput, L3p2:iron_gear_wheel_throughput; лечит: стройку не там и перевёрнутые инсертеры]
12. Ленты ставь по одному тайлу с явным направлением; connect_entities лентами петляет. Перед длинной трассой проверь, нет ли на пути озера: get_resource_patch(Resource.Water, середина трассы). Обходи его вручную. [L3p1, L3p2:inserter_throughput, L3p2:electronic_circuit_throughput; лечит: разрывы на воде]

Электросеть
13. connect_entities с MediumElectricPole иногда работает, но может оставить дыру или отдельную группу с voltage=0. После стройки проверь, что ElectricityGroup ровно одна, и найди сущности с NO_POWER или NOT_PLUGGED_IN, включая каждый двигатель. Покрытие столба ~3.5 тайла, провод тянется ~9 тайлов. [L3p2:iron_gear_wheel_throughput, L3p2:automation_science_pack_throughput, L3p2:electronic_circuit_throughput; лечит: обесточенные машины]

Проверки
14. Первый замер завышен из-за буфера (53 против реальных 23). Перемерь через 60 с. [L3p2:electronic_circuit_throughput; лечит: завышенную оценку]
15. Burner-инсертер котла в статусе WAITING_FOR_SPACE с предупреждением «item on the ground» работает нормально. Суди о нём по уровню топлива в котле. [L3p2:iron_plate_throughput; лечит: ложную тревогу]
16. Песочница запрещает getattr, import и двойные подчёркивания. Печатай только проблемные статусы, группы и топливо котла: get_entities() по всем лентам переполняет вывод. [L3p1, L3p2:logistics_science_pack_throughput; лечит: отклонённый код и потерю вывода]