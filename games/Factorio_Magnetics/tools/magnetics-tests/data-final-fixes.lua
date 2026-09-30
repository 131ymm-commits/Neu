-- Выгрузка прототипов мода (имена с magnetics-, кроме тестовых) и изменённых ванильных — в лог, для tools/check_props.py.
local out = {}
local touched = { ["transport-belt"] = {"express-transport-belt", "turbo-transport-belt"}, ["underground-belt"] = {"express-underground-belt", "turbo-underground-belt"},
                  ["splitter"] = {"express-splitter", "turbo-splitter"}, ["mining-drill"] = {"electric-mining-drill"}, ["accumulator"] = {"accumulator"},
                  ["electric-pole"] = {"substation"}, ["wall"] = {"stone-wall"} }
for t, list in pairs(data.raw) do
  for n, p in pairs(list) do
    if n:sub(1, 10) == "magnetics-" and n:sub(1, 15) ~= "magnetics-test-" then
      out[t] = out[t] or {}; out[t][n] = p
    end
  end
end
for t, names in pairs(touched) do
  for _, n in pairs(names) do
    if data.raw[t] and data.raw[t][n] then out[t] = out[t] or {}; out[t][n] = data.raw[t][n] end
  end
end
log("MAGNETICS_RAW_BEGIN" .. helpers.table_to_json(out) .. "MAGNETICS_RAW_END")
