/* LINUX-01: маленькая замена KUnit для прогона тестов модулей вне ядра. Только макросы, которые используют
 * тесты шести модулей пилота: KUNIT_EXPECT_EQ(_MSG), KUNIT_EXPECT_PTR_EQ(_MSG), KUNIT_EXPECT_NULL, KUNIT_EXPECT_STREQ,
 * KUNIT_ASSERT_NOT_NULL, KUNIT_CASE, KUNIT_CASE_PARAM, KUNIT_ARRAY_PARAM, kunit_test_suite(s). Исполнитель — kunit_runner.c. */
#pragma once

#define KUNIT_PARAM_DESC_SIZE 128

struct kunit {
	const void *param_value;
	int expectations;
	int failures;
};

typedef const void *(*kunit_gen_params_t)(const void *prev, char *desc);

struct kunit_case {
	void (*run_case)(struct kunit *test);
	const char *name;
	kunit_gen_params_t generate_params;
};

struct kunit_suite {
	const char *name;
	struct kunit_case *test_cases;
};

void kunit_record(struct kunit *test, int ok, const char *file, int line, const char *what, const char *fmt, ...);
void kunit_register_suites(struct kunit_suite **suites);

#define KUNIT_CASE(f) { .run_case = f, .name = #f, .generate_params = 0 }
#define KUNIT_CASE_PARAM(f, gen) { .run_case = f, .name = #f, .generate_params = gen }

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

#define KUNIT_EXPECT_EQ_MSG(test, left, right, fmt, ...) \
	kunit_record(test, (left) == (right), __FILE__, __LINE__, "EXPECT_EQ(" #left ", " #right ")", fmt, ##__VA_ARGS__)
#define KUNIT_EXPECT_EQ(test, left, right) KUNIT_EXPECT_EQ_MSG(test, left, right, "")
#define KUNIT_EXPECT_PTR_EQ_MSG(test, left, right, fmt, ...) \
	kunit_record(test, (const void *)(left) == (const void *)(right), __FILE__, __LINE__, \
		     "EXPECT_PTR_EQ(" #left ", " #right ")", fmt, ##__VA_ARGS__)
#define KUNIT_EXPECT_PTR_EQ(test, left, right) KUNIT_EXPECT_PTR_EQ_MSG(test, left, right, "")
#define KUNIT_EXPECT_NULL(test, p) KUNIT_EXPECT_PTR_EQ_MSG(test, p, 0, "")
#define KUNIT_EXPECT_STREQ(test, left, right) do {                                                     \
		const char *__l = (left), *__r = (right);                                              \
		kunit_record(test, __l && __r && strcmp(__l, __r) == 0, __FILE__, __LINE__,             \
			     "EXPECT_STREQ(" #left ", " #right ")", "");                               \
	} while (0)
#define KUNIT_ASSERT_NOT_NULL(test, p) do {                                                            \
		const void *__p = (const void *)(p);                                                   \
		kunit_record(test, __p != 0, __FILE__, __LINE__, "ASSERT_NOT_NULL(" #p ")", "");        \
		if (!__p)                                                                              \
			return;                                                                        \
	} while (0)

#define __KUNIT_CAT2(a, b) a##b
#define __KUNIT_CAT(a, b) __KUNIT_CAT2(a, b)
#define kunit_test_suites(...)                                                                         \
	static struct kunit_suite *__KUNIT_CAT(__kunit_suites_, __LINE__)[] = { __VA_ARGS__, 0 };      \
	__attribute__((constructor)) static void __KUNIT_CAT(__kunit_reg_, __LINE__)(void)            \
	{ kunit_register_suites(__KUNIT_CAT(__kunit_suites_, __LINE__)); }
#define kunit_test_suite(suite) kunit_test_suites(&suite)
