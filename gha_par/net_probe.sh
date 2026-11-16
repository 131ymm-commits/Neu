#!/bin/bash
# Проба сети раннера (16.11.2026): проба GitHub Models (gha_out/ai_probe) на все запросы получила «OK\r\n», text/plain, за 0,2 с —
# похоже на перехват. Смотрим: переменные прокси (только имена), DNS, удалённый адрес, код и тип ответа, выдавший сертификат.
# Токен раннера уходит только на адреса GitHub (models.github.ai, api.github.com); на чужие адреса — без заголовка.
set -uo pipefail
OUT="$1"
{
echo "== переменные прокси (только имена)"; env | grep -i -E '^(https?|no|all)_proxy=' | sed 's/=.*/=<задано>/' || echo "нет"
echo "== DNS"; for h in models.github.ai api.github.com models.inference.ai.azure.com pypi.org example.com; do echo "$h -> $(getent hosts "$h" | head -2 | tr '\n' ' ')"; done
echo "== /etc/resolv.conf"; grep -v '^#' /etc/resolv.conf | head -5
for u in https://models.github.ai/catalog/models https://api.github.com/meta; do
  echo "== $u (с токеном раннера)"
  curl -sS -m 25 -o /tmp/b -w 'ip %{remote_ip} код %{http_code} тип %{content_type} байт %{size_download}\n' -H "Authorization: Bearer $GH_MODELS_TOKEN" -H 'Accept: application/vnd.github+json' "$u" 2>&1
  echo "-- начало тела: $(head -c 160 /tmp/b | tr -d '\r' | tr '\n' ' ')"
done
for u in https://models.github.ai/ https://pypi.org/simple/numpy/ https://example.com/; do
  echo "== $u (без токена)"
  curl -sS -m 25 -o /tmp/b -w 'ip %{remote_ip} код %{http_code} тип %{content_type} байт %{size_download}\n' "$u" 2>&1
  echo "-- начало тела: $(head -c 120 /tmp/b | tr -d '\r' | tr '\n' ' ')"
done
for h in models.github.ai api.github.com example.com; do
  echo "== сертификат $h"; echo | timeout 20 openssl s_client -connect "$h:443" -servername "$h" 2>/dev/null | openssl x509 -noout -subject -issuer 2>/dev/null || echo "нет"
done
} > "$OUT/net_probe.txt" 2>&1
cat "$OUT/net_probe.txt"
