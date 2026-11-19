/* LINUX-02: сравнение перевода lib/crypto/md5.c с оригиналом. Сообщение — до 1000 байт (в режиме границ — длины у границ
 * блока 64 и места длины 56), делится на случайные части. После каждого md5_update сравнивается определённая часть
 * md5_ctx (state, bytecount, буфер до bytecount % 64), после md5_final — весь контекст и дайджест. HMAC: ключи 0…200 байт,
 * подготовленный ключ (hmac_md5_key) сравнивается побайтно. hmac_md5_update — встроенная функция заголовка: у оригинала
 * вызывается её копия над orig_md5_update. */
#include <crypto/md5.h>
#include "diff_common.h"

void orig_md5_init(struct md5_ctx *ctx);
void orig_md5_update(struct md5_ctx *ctx, const u8 *data, size_t len);
void orig_md5_final(struct md5_ctx *ctx, u8 out[MD5_DIGEST_SIZE]);
void orig_md5(const u8 *data, size_t len, u8 out[MD5_DIGEST_SIZE]);
void orig_hmac_md5_preparekey(struct hmac_md5_key *key, const u8 *raw_key, size_t raw_key_len);
void orig_hmac_md5_init(struct hmac_md5_ctx *ctx, const struct hmac_md5_key *key);
void orig_hmac_md5_init_usingrawkey(struct hmac_md5_ctx *ctx, const u8 *raw_key, size_t raw_key_len);
void orig_hmac_md5_final(struct hmac_md5_ctx *ctx, u8 out[MD5_DIGEST_SIZE]);
void orig_hmac_md5(const struct hmac_md5_key *key, const u8 *data, size_t data_len, u8 out[MD5_DIGEST_SIZE]);
void orig_hmac_md5_usingrawkey(const u8 *raw_key, size_t raw_key_len, const u8 *data, size_t data_len, u8 out[MD5_DIGEST_SIZE]);
static void orig_hmac_md5_update(struct hmac_md5_ctx *ctx, const u8 *data, size_t data_len) { orig_md5_update(&ctx->hash_ctx, data, data_len); }

static int ctx_eq(const struct md5_ctx *a, const struct md5_ctx *b)
{
	if (memcmp(&a->state, &b->state, sizeof(a->state)) || a->bytecount != b->bytecount)
		return 0;
	return memcmp(a->buf, b->buf, (size_t)(a->bytecount % MD5_BLOCK_SIZE)) == 0;
}

static size_t msg_len(void) { return g_boundary ? pick_len(200, 64) : (size_t)rnd_below(1001); }

static int c_stream(char *ex, size_t exn)
{
	static u8 msg[1100];
	size_t len = msg_len();
	rand_fill(msg, len);
	struct md5_ctx a, b;
	memset(&a, 0x5A, sizeof(a));
	memset(&b, 0x5A, sizeof(b));
	orig_md5_init(&a);
	md5_init(&b);
	if (!ctx_eq(&a, &b))
		DIFF_EX("md5_init: разные контексты");
	size_t pos = 0;
	while (pos < len || (pos == len && rnd() % 4 == 0)) {
		size_t part = (pos == len) ? 0 : 1 + rnd_below(len - pos < 130 ? len - pos : 130);
		orig_md5_update(&a, msg + pos, part);
		md5_update(&b, msg + pos, part);
		if (!ctx_eq(&a, &b))
			DIFF_EX("md5_update: длина %zu, позиция %zu, часть %zu — разные контексты (bytecount %llu против %llu)", len, pos, part,
				(unsigned long long)a.bytecount, (unsigned long long)b.bytecount);
		pos += part;
		if (part == 0)
			break;
	}
	u8 da[MD5_DIGEST_SIZE], db[MD5_DIGEST_SIZE];
	orig_md5_final(&a, da);
	md5_final(&b, db);
	if (memcmp(da, db, sizeof(da)))
		DIFF_EX("md5_final: длина %zu — разные дайджесты", len);
	if (memcmp(&a, &b, sizeof(a)))
		DIFF_EX("md5_final: длина %zu — контекст после final разный", len);
	return 0;
}

static int c_oneshot(char *ex, size_t exn)
{
	static u8 msg[1100];
	size_t len = msg_len(), off = rnd_below(8);
	rand_fill(msg + off, len);
	u8 da[MD5_DIGEST_SIZE], db[MD5_DIGEST_SIZE];
	orig_md5(msg + off, len, da);
	md5(msg + off, len, db);
	if (memcmp(da, db, sizeof(da)))
		DIFF_EX("md5: длина %zu, смещение %zu — разные дайджесты", len, off);
	return 0;
}

static int c_hmac(char *ex, size_t exn)
{
	static u8 key[220], msg[1100];
	size_t klen = g_boundary ? pick_len(200, 64) : rnd_below(201), len = msg_len();
	rand_fill(key, klen);
	rand_fill(msg, len);
	struct hmac_md5_key ka, kb;
	memset(&ka, 0x33, sizeof(ka));
	memset(&kb, 0x33, sizeof(kb));
	orig_hmac_md5_preparekey(&ka, key, klen);
	hmac_md5_preparekey(&kb, key, klen);
	if (memcmp(&ka, &kb, sizeof(ka)))
		DIFF_EX("hmac_md5_preparekey: ключ %zu байт — разные подготовленные ключи", klen);
	struct hmac_md5_ctx a, b;
	int raw = rnd() % 2;
	memset(&a, 0x44, sizeof(a));
	memset(&b, 0x44, sizeof(b));
	if (raw) { orig_hmac_md5_init_usingrawkey(&a, key, klen); hmac_md5_init_usingrawkey(&b, key, klen); }
	else { orig_hmac_md5_init(&a, &ka); hmac_md5_init(&b, &kb); }
	if (!ctx_eq(&a.hash_ctx, &b.hash_ctx) || memcmp(&a.ostate, &b.ostate, sizeof(a.ostate)))
		DIFF_EX("hmac_md5_init%s: ключ %zu байт — разные контексты", raw ? "_usingrawkey" : "", klen);
	size_t pos = 0;
	while (pos < len) {
		size_t part = 1 + rnd_below(len - pos < 130 ? len - pos : 130);
		orig_hmac_md5_update(&a, msg + pos, part);
		hmac_md5_update(&b, msg + pos, part);
		pos += part;
	}
	u8 da[MD5_DIGEST_SIZE], db[MD5_DIGEST_SIZE];
	orig_hmac_md5_final(&a, da);
	hmac_md5_final(&b, db);
	if (memcmp(da, db, sizeof(da)))
		DIFF_EX("hmac_md5_final: ключ %zu, сообщение %zu — разные результаты", klen, len);
	if (memcmp(&a, &b, sizeof(a)))
		DIFF_EX("hmac_md5_final: контекст после final разный");
	orig_hmac_md5(&ka, msg, len, da);
	hmac_md5(&kb, msg, len, db);
	if (memcmp(da, db, sizeof(da)))
		DIFF_EX("hmac_md5: ключ %zu, сообщение %zu — разные результаты", klen, len);
	orig_hmac_md5_usingrawkey(key, klen, msg, len, da);
	hmac_md5_usingrawkey(key, klen, msg, len, db);
	if (memcmp(da, db, sizeof(da)))
		DIFF_EX("hmac_md5_usingrawkey: ключ %zu, сообщение %zu — разные результаты", klen, len);
	return 0;
}

int main(int argc, char **argv)
{
	static const struct fn L[] = { { "md5_stream", c_stream }, { "md5_oneshot", c_oneshot }, { "hmac_md5", c_hmac } };
	return diff_main(L, 3, argc, argv);
}
