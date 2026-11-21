/* LINUX-01: функции ядра, нужные модулям и тестам, перенесены из исходников ядра 7.4-rc3:
 * lib/kstrtox.c (_parse_integer_fixup_radix, _parse_integer_limit), lib/vsprintf.c (simple_strntoull, simple_strtoull,
 * simple_strtoul, simple_strtol), lib/string_helpers.c (skip_spaces), lib/string.c (memchr_inv — побайтно, тот же результат).
 * strscpy и get_random_u8 — упрощённые (нужны только тестам). SPDX: GPL-2.0, как исходники ядра. */
#include <stdlib.h>

#define KSTRTOX_OVERFLOW (1U << 31)

static const char *_parse_integer_fixup_radix(const char *s, unsigned int *base)
{
	if (*base == 0) {
		if (s[0] == '0') {
			if (_tolower(s[1]) == 'x' && isxdigit(s[2]))
				*base = 16;
			else
				*base = 8;
		} else
			*base = 10;
	}
	if (*base == 16 && s[0] == '0' && _tolower(s[1]) == 'x')
		s += 2;
	return s;
}

static unsigned int _parse_integer_limit(const char *s, unsigned int base, unsigned long long *p,
					 size_t max_chars, unsigned long long init)
{
	unsigned int rv, overflow = 0;
	unsigned long long res;

	res = init;
	for (rv = 0; rv < max_chars; rv++, s++) {
		unsigned int c = (unsigned char)*s;
		unsigned int lc = _tolower(c);
		unsigned int val;

		if (isdigit(c))
			val = c - '0';
		else if ('a' <= lc && lc <= 'f')
			val = lc - 'a' + 10;
		else
			break;

		if (val >= base)
			break;
		if (unlikely(res & (~0ull << 60))) {
			if (check_mul_overflow(res, base, &res) ||
			    check_add_overflow(res, val, &res)) {
				res = ULLONG_MAX;
				overflow = KSTRTOX_OVERFLOW;
			}
		} else {
			res = res * base + val;
		}
	}
	*p = res;
	return rv | overflow;
}

static unsigned long long simple_strntoull(const char *startp, char **endp, unsigned int base, size_t max_chars)
{
	const char *cp;
	unsigned long long result = 0ULL;
	size_t prefix_chars;
	unsigned int rv;

	cp = _parse_integer_fixup_radix(startp, &base);
	prefix_chars = cp - startp;
	if (prefix_chars < max_chars) {
		rv = _parse_integer_limit(cp, base, &result, max_chars - prefix_chars, 0);
		cp += (rv & ~KSTRTOX_OVERFLOW);
	} else {
		cp = startp + max_chars;
	}

	if (endp)
		*endp = (char *)cp;

	return result;
}

unsigned long long simple_strtoull(const char *cp, char **endp, unsigned int base)
{
	return simple_strntoull(cp, endp, base, INT_MAX);
}

unsigned long simple_strtoul(const char *cp, char **endp, unsigned int base)
{
	return simple_strtoull(cp, endp, base);
}

long simple_strtol(const char *cp, char **endp, unsigned int base)
{
	if (*cp == '-')
		return -simple_strtoul(cp + 1, endp, base);

	return simple_strtoul(cp, endp, base);
}

char *skip_spaces(const char *str)
{
	while (isspace(*str))
		++str;
	return (char *)str;
}

void *memchr_inv(const void *start, int c, size_t bytes)
{
	const u8 *p = start;
	u8 value = (u8)c;
	for (size_t i = 0; i < bytes; i++)
		if (p[i] != value)
			return (void *)(p + i);
	return NULL;
}

ssize_t strscpy(char *dest, const char *src, size_t count)
{
	size_t n = strlen(src);
	if (count == 0)
		return -7;
	if (n >= count) {
		memcpy(dest, src, count - 1);
		dest[count - 1] = '\0';
		return -7;			/* -E2BIG */
	}
	memcpy(dest, src, n + 1);
	return (ssize_t)n;
}

static u64 __rng = 0x9E3779B97F4A7C15ULL;
u8 get_random_u8(void)
{
	__rng ^= __rng << 13;
	__rng ^= __rng >> 7;
	__rng ^= __rng << 17;
	return (u8)(__rng >> 24);
}
