/* LINUX-02: замена KUnit для прогона тестов модулей вне ядра (исполнитель — harness/kunit_runner.c). Расширение LINUX-01:
 * все виды EXPECT/ASSERT, которые встречаются в тестах шести модулей (и их _MSG), MEMEQ/STREQ, skip, kunit_kzalloc,
 * параметры (KUNIT_ARRAY_PARAM, KUNIT_ARRAY_PARAM_DESC), init/exit набора и случая.
 * Каждое утверждение считается (kunit_record): случай без единого утверждения исполнитель помечает «пустым» (план пилота).
 * ASSERT при провале прекращает случай (kunit_abort_case). */
#pragma once
#include <stdarg.h>

#define KUNIT_PARAM_DESC_SIZE 128

struct kunit_case;
struct kunit {
	const void *param_value;
	void *priv;
	int expectations;
	int failures;
	int skipped;
	const char *name;
};

typedef const void *(*kunit_gen_params_t)(const void *prev, char *desc);

struct kunit_case {
	void (*run_case)(struct kunit *test);
	const char *name;
	kunit_gen_params_t generate_params;
};

struct kunit_suite {
	const char *name;
	int (*suite_init)(struct kunit_suite *suite);
	void (*suite_exit)(struct kunit_suite *suite);
	int (*init)(struct kunit *test);
	void (*exit)(struct kunit *test);
	struct kunit_case *test_cases;
};

void kunit_record(struct kunit *test, int ok, const char *file, int line, const char *what, const char *fmt, ...);
void kunit_abort_case(struct kunit *test) __attribute__((noreturn));
void kunit_skip_case(struct kunit *test, const char *fmt, ...) __attribute__((noreturn));
void kunit_register_suites(struct kunit_suite **suites);
void *kunit_kmalloc(struct kunit *test, size_t size, gfp_t gfp);
void *kunit_kzalloc(struct kunit *test, size_t size, gfp_t gfp);
void *kunit_kmalloc_array(struct kunit *test, size_t n, size_t size, gfp_t gfp);
#define kunit_kcalloc(test, n, size, gfp) kunit_kzalloc((test), (n) * (size), (gfp))
#define kunit_kfree(test, p) ((void)(test), (void)(p))

#define kunit_info(test, fmt, ...) ((void)(test))
#define kunit_warn(test, fmt, ...) ((void)(test))
#define kunit_err(test, fmt, ...) ((void)(test))
#define kunit_log(lvl, test, fmt, ...) ((void)(test))
#define kunit_skip(test, fmt, ...) kunit_skip_case((test), fmt, ##__VA_ARGS__)
#define kunit_mark_skipped(test, fmt, ...) do { (test)->skipped = 1; } while (0)

#define KUNIT_CASE(f) { .run_case = f, .name = #f, .generate_params = 0 }
#define KUNIT_CASE_PARAM(f, gen) { .run_case = f, .name = #f, .generate_params = gen }
#define KUNIT_CASE_SLOW(f) KUNIT_CASE(f)

#define KUNIT_ARRAY_PARAM(name, array, get_desc)                                                      \
	static const void *name##_gen_params(const void *prev, char *desc)                            \
	{                                                                                              \
		__typeof__((array)[0]) *__next = prev ? ((__typeof__(__next))prev) + 1 : (array);     \
		if ((size_t)(__next - (array)) < ARRAY_SIZE((array))) {                                \
			void (*__get_desc)(__typeof__(__next), char *) = get_desc;                     \
			if (__get_desc)                                                                \
				__get_desc(__next, desc);                                              \
			return __next;                                                                 \
		}                                                                                      \
		return 0;                                                                              \
	}
#define KUNIT_ARRAY_PARAM_DESC(name, array, desc_member)                                              \
	static const void *name##_gen_params(const void *prev, char *desc)                            \
	{                                                                                              \
		__typeof__((array)[0]) *__next = prev ? ((__typeof__(__next))prev) + 1 : (array);     \
		if ((size_t)(__next - (array)) < ARRAY_SIZE((array))) {                                \
			strscpy(desc, __next->desc_member, KUNIT_PARAM_DESC_SIZE);                     \
			return __next;                                                                 \
		}                                                                                      \
		return 0;                                                                              \
	}

/* одно утверждение: abort = 1 у ASSERT */
#define __KUNIT_CHECK(test, abort, ok, what, fmt, ...) do {                                            \
		int __ok = !!(ok);                                                                     \
		kunit_record((test), __ok, __FILE__, __LINE__, what, fmt, ##__VA_ARGS__);              \
		if (!__ok && (abort))                                                                  \
			kunit_abort_case(test);                                                        \
	} while (0)
#define __KUNIT_BIN(test, abort, l, op, r, name, fmt, ...) do {                                        \
		__typeof__(l) __l = (l); __typeof__(r) __r = (r);                                      \
		__KUNIT_CHECK(test, abort, __l op __r, name "(" #l ", " #r ")", fmt, ##__VA_ARGS__);    \
	} while (0)
#define __KUNIT_PTR(test, abort, l, op, r, name, fmt, ...) do {                                        \
		const void *__l = (const void *)(l), *__r = (const void *)(r);                         \
		__KUNIT_CHECK(test, abort, __l op __r, name "(" #l ", " #r ")", fmt, ##__VA_ARGS__);    \
	} while (0)
#define __KUNIT_STR(test, abort, l, r, eq, name, fmt, ...) do {                                        \
		const char *__l = (l), *__r = (r);                                                     \
		int __e = __l && __r && strcmp(__l, __r) == 0;                                         \
		__KUNIT_CHECK(test, abort, (eq) ? __e : (__l && __r && !__e), name "(" #l ", " #r ")", fmt, ##__VA_ARGS__); \
	} while (0)
#define __KUNIT_MEM(test, abort, l, r, n, eq, name, fmt, ...) do {                                     \
		const void *__l = (l), *__r = (r); size_t __n = (n);                                   \
		int __e = __l && __r && memcmp(__l, __r, __n) == 0;                                    \
		__KUNIT_CHECK(test, abort, (eq) ? __e : (__l && __r && !__e), name "(" #l ", " #r ")", fmt, ##__VA_ARGS__); \
	} while (0)

#define KUNIT_FAIL(test, fmt, ...) __KUNIT_CHECK(test, 0, 0, "FAIL", fmt, ##__VA_ARGS__)
#define KUNIT_SUCCEED(test) __KUNIT_CHECK(test, 0, 1, "SUCCEED", "")

#define KUNIT_EXPECT_TRUE_MSG(test, c, fmt, ...) __KUNIT_CHECK(test, 0, (c), "EXPECT_TRUE(" #c ")", fmt, ##__VA_ARGS__)
#define KUNIT_EXPECT_FALSE_MSG(test, c, fmt, ...) __KUNIT_CHECK(test, 0, !(c), "EXPECT_FALSE(" #c ")", fmt, ##__VA_ARGS__)
#define KUNIT_ASSERT_TRUE_MSG(test, c, fmt, ...) __KUNIT_CHECK(test, 1, (c), "ASSERT_TRUE(" #c ")", fmt, ##__VA_ARGS__)
#define KUNIT_ASSERT_FALSE_MSG(test, c, fmt, ...) __KUNIT_CHECK(test, 1, !(c), "ASSERT_FALSE(" #c ")", fmt, ##__VA_ARGS__)
#define KUNIT_EXPECT_TRUE(test, c) KUNIT_EXPECT_TRUE_MSG(test, c, "")
#define KUNIT_EXPECT_FALSE(test, c) KUNIT_EXPECT_FALSE_MSG(test, c, "")
#define KUNIT_ASSERT_TRUE(test, c) KUNIT_ASSERT_TRUE_MSG(test, c, "")
#define KUNIT_ASSERT_FALSE(test, c) KUNIT_ASSERT_FALSE_MSG(test, c, "")

#define KUNIT_EXPECT_EQ_MSG(test, l, r, fmt, ...) __KUNIT_BIN(test, 0, l, ==, r, "EXPECT_EQ", fmt, ##__VA_ARGS__)
#define KUNIT_EXPECT_NE_MSG(test, l, r, fmt, ...) __KUNIT_BIN(test, 0, l, !=, r, "EXPECT_NE", fmt, ##__VA_ARGS__)
#define KUNIT_EXPECT_LT_MSG(test, l, r, fmt, ...) __KUNIT_BIN(test, 0, l, <, r, "EXPECT_LT", fmt, ##__VA_ARGS__)
#define KUNIT_EXPECT_LE_MSG(test, l, r, fmt, ...) __KUNIT_BIN(test, 0, l, <=, r, "EXPECT_LE", fmt, ##__VA_ARGS__)
#define KUNIT_EXPECT_GT_MSG(test, l, r, fmt, ...) __KUNIT_BIN(test, 0, l, >, r, "EXPECT_GT", fmt, ##__VA_ARGS__)
#define KUNIT_EXPECT_GE_MSG(test, l, r, fmt, ...) __KUNIT_BIN(test, 0, l, >=, r, "EXPECT_GE", fmt, ##__VA_ARGS__)
#define KUNIT_ASSERT_EQ_MSG(test, l, r, fmt, ...) __KUNIT_BIN(test, 1, l, ==, r, "ASSERT_EQ", fmt, ##__VA_ARGS__)
#define KUNIT_ASSERT_NE_MSG(test, l, r, fmt, ...) __KUNIT_BIN(test, 1, l, !=, r, "ASSERT_NE", fmt, ##__VA_ARGS__)
#define KUNIT_ASSERT_LT_MSG(test, l, r, fmt, ...) __KUNIT_BIN(test, 1, l, <, r, "ASSERT_LT", fmt, ##__VA_ARGS__)
#define KUNIT_ASSERT_LE_MSG(test, l, r, fmt, ...) __KUNIT_BIN(test, 1, l, <=, r, "ASSERT_LE", fmt, ##__VA_ARGS__)
#define KUNIT_ASSERT_GT_MSG(test, l, r, fmt, ...) __KUNIT_BIN(test, 1, l, >, r, "ASSERT_GT", fmt, ##__VA_ARGS__)
#define KUNIT_ASSERT_GE_MSG(test, l, r, fmt, ...) __KUNIT_BIN(test, 1, l, >=, r, "ASSERT_GE", fmt, ##__VA_ARGS__)
#define KUNIT_EXPECT_EQ(test, l, r) KUNIT_EXPECT_EQ_MSG(test, l, r, "")
#define KUNIT_EXPECT_NE(test, l, r) KUNIT_EXPECT_NE_MSG(test, l, r, "")
#define KUNIT_EXPECT_LT(test, l, r) KUNIT_EXPECT_LT_MSG(test, l, r, "")
#define KUNIT_EXPECT_LE(test, l, r) KUNIT_EXPECT_LE_MSG(test, l, r, "")
#define KUNIT_EXPECT_GT(test, l, r) KUNIT_EXPECT_GT_MSG(test, l, r, "")
#define KUNIT_EXPECT_GE(test, l, r) KUNIT_EXPECT_GE_MSG(test, l, r, "")
#define KUNIT_ASSERT_EQ(test, l, r) KUNIT_ASSERT_EQ_MSG(test, l, r, "")
#define KUNIT_ASSERT_NE(test, l, r) KUNIT_ASSERT_NE_MSG(test, l, r, "")
#define KUNIT_ASSERT_LT(test, l, r) KUNIT_ASSERT_LT_MSG(test, l, r, "")
#define KUNIT_ASSERT_LE(test, l, r) KUNIT_ASSERT_LE_MSG(test, l, r, "")
#define KUNIT_ASSERT_GT(test, l, r) KUNIT_ASSERT_GT_MSG(test, l, r, "")
#define KUNIT_ASSERT_GE(test, l, r) KUNIT_ASSERT_GE_MSG(test, l, r, "")

#define KUNIT_EXPECT_PTR_EQ_MSG(test, l, r, fmt, ...) __KUNIT_PTR(test, 0, l, ==, r, "EXPECT_PTR_EQ", fmt, ##__VA_ARGS__)
#define KUNIT_EXPECT_PTR_NE_MSG(test, l, r, fmt, ...) __KUNIT_PTR(test, 0, l, !=, r, "EXPECT_PTR_NE", fmt, ##__VA_ARGS__)
#define KUNIT_ASSERT_PTR_EQ_MSG(test, l, r, fmt, ...) __KUNIT_PTR(test, 1, l, ==, r, "ASSERT_PTR_EQ", fmt, ##__VA_ARGS__)
#define KUNIT_EXPECT_PTR_EQ(test, l, r) KUNIT_EXPECT_PTR_EQ_MSG(test, l, r, "")
#define KUNIT_EXPECT_PTR_NE(test, l, r) KUNIT_EXPECT_PTR_NE_MSG(test, l, r, "")
#define KUNIT_ASSERT_PTR_EQ(test, l, r) KUNIT_ASSERT_PTR_EQ_MSG(test, l, r, "")
#define KUNIT_EXPECT_NULL(test, p) __KUNIT_CHECK(test, 0, (const void *)(p) == 0, "EXPECT_NULL(" #p ")", "")
#define KUNIT_EXPECT_NOT_NULL(test, p) __KUNIT_CHECK(test, 0, (const void *)(p) != 0, "EXPECT_NOT_NULL(" #p ")", "")
#define KUNIT_ASSERT_NULL(test, p) __KUNIT_CHECK(test, 1, (const void *)(p) == 0, "ASSERT_NULL(" #p ")", "")
#define KUNIT_ASSERT_NOT_NULL(test, p) __KUNIT_CHECK(test, 1, (const void *)(p) != 0, "ASSERT_NOT_NULL(" #p ")", "")
#define KUNIT_EXPECT_NOT_ERR_OR_NULL(test, p) __KUNIT_CHECK(test, 0, !IS_ERR_OR_NULL(p), "EXPECT_NOT_ERR_OR_NULL(" #p ")", "")
#define KUNIT_ASSERT_NOT_ERR_OR_NULL(test, p) __KUNIT_CHECK(test, 1, !IS_ERR_OR_NULL(p), "ASSERT_NOT_ERR_OR_NULL(" #p ")", "")

#define KUNIT_EXPECT_STREQ_MSG(test, l, r, fmt, ...) __KUNIT_STR(test, 0, l, r, 1, "EXPECT_STREQ", fmt, ##__VA_ARGS__)
#define KUNIT_EXPECT_STRNEQ_MSG(test, l, r, fmt, ...) __KUNIT_STR(test, 0, l, r, 0, "EXPECT_STRNEQ", fmt, ##__VA_ARGS__)
#define KUNIT_ASSERT_STREQ_MSG(test, l, r, fmt, ...) __KUNIT_STR(test, 1, l, r, 1, "ASSERT_STREQ", fmt, ##__VA_ARGS__)
#define KUNIT_EXPECT_STREQ(test, l, r) KUNIT_EXPECT_STREQ_MSG(test, l, r, "")
#define KUNIT_EXPECT_STRNEQ(test, l, r) KUNIT_EXPECT_STRNEQ_MSG(test, l, r, "")
#define KUNIT_ASSERT_STREQ(test, l, r) KUNIT_ASSERT_STREQ_MSG(test, l, r, "")

#define KUNIT_EXPECT_MEMEQ_MSG(test, l, r, n, fmt, ...) __KUNIT_MEM(test, 0, l, r, n, 1, "EXPECT_MEMEQ", fmt, ##__VA_ARGS__)
#define KUNIT_EXPECT_MEMNEQ_MSG(test, l, r, n, fmt, ...) __KUNIT_MEM(test, 0, l, r, n, 0, "EXPECT_MEMNEQ", fmt, ##__VA_ARGS__)
#define KUNIT_ASSERT_MEMEQ_MSG(test, l, r, n, fmt, ...) __KUNIT_MEM(test, 1, l, r, n, 1, "ASSERT_MEMEQ", fmt, ##__VA_ARGS__)
#define KUNIT_EXPECT_MEMEQ(test, l, r, n) KUNIT_EXPECT_MEMEQ_MSG(test, l, r, n, "")
#define KUNIT_EXPECT_MEMNEQ(test, l, r, n) KUNIT_EXPECT_MEMNEQ_MSG(test, l, r, n, "")
#define KUNIT_ASSERT_MEMEQ(test, l, r, n) KUNIT_ASSERT_MEMEQ_MSG(test, l, r, n, "")

#define __KUNIT_CAT2(a, b) a##b
#define __KUNIT_CAT(a, b) __KUNIT_CAT2(a, b)
#define kunit_test_suites(...)                                                                         \
	static struct kunit_suite *__KUNIT_CAT(__kunit_suites_, __LINE__)[] = { __VA_ARGS__, 0 };      \
	__attribute__((constructor)) static void __KUNIT_CAT(__kunit_reg_, __LINE__)(void)            \
	{ kunit_register_suites(__KUNIT_CAT(__kunit_suites_, __LINE__)); }
#define kunit_test_suite(suite) kunit_test_suites(&suite)
#define kunit_test_init_section_suites(...) kunit_test_suites(__VA_ARGS__)
