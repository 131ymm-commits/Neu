use core::ffi::c_ulong;
use core::mem::size_of;
use core::ptr;

pub const MD5_DIGEST_SIZE: usize = 16;
pub const MD5_HMAC_BLOCK_SIZE: usize = 64;
pub const MD5_BLOCK_SIZE: usize = 64;
pub const MD5_BLOCK_WORDS: usize = 16;
pub const MD5_HASH_WORDS: usize = 4;
pub const MD5_STATE_SIZE: usize = 24;

pub const MD5_H0: c_ulong = 0x67452301;
pub const MD5_H1: c_ulong = 0xefcdab89;
pub const MD5_H2: c_ulong = 0x98badcfe;
pub const MD5_H3: c_ulong = 0x10325476;

pub const HMAC_IPAD_VALUE: u8 = 0x36;
pub const HMAC_OPAD_VALUE: u8 = 0x5c;

#[repr(C)]
#[derive(Clone, Copy)]
pub struct md5_state {
    pub hash: [u32; MD5_HASH_WORDS],
    pub byte_count: u64,
    pub block: [u32; MD5_BLOCK_WORDS],
}

#[repr(C)]
#[derive(Clone, Copy)]
pub struct md5_block_state {
    pub h: [u32; MD5_HASH_WORDS],
}

/// `u8 buf[MD5_BLOCK_SIZE] __aligned(__alignof__(__le64))`
#[repr(C, align(8))]
#[derive(Clone, Copy)]
pub struct Md5Buf(pub [u8; MD5_BLOCK_SIZE]);

#[repr(C)]
#[derive(Clone, Copy)]
pub struct md5_ctx {
    pub state: md5_block_state,
    pub bytecount: u64,
    pub buf: Md5Buf,
}

#[repr(C)]
#[derive(Clone, Copy)]
pub struct hmac_md5_key {
    pub istate: md5_block_state,
    pub ostate: md5_block_state,
}

#[repr(C)]
#[derive(Clone, Copy)]
pub struct hmac_md5_ctx {
    pub hash_ctx: md5_ctx,
    pub ostate: md5_block_state,
}

const _: () = assert!(size_of::<md5_ctx>() == 88);
const _: () = assert!(core::mem::align_of::<md5_ctx>() == 8);
const _: () = assert!(size_of::<hmac_md5_ctx>() == 104);
const _: () = assert!(size_of::<hmac_md5_key>() == 32);

static MD5_IV: md5_block_state = md5_block_state {
    h: [MD5_H0 as u32, MD5_H1 as u32, MD5_H2 as u32, MD5_H3 as u32],
};

/// Zero `n` bytes at `p` in a way the compiler cannot elide.
unsafe fn memzero_explicit(p: *mut u8, n: usize) {
    for i in 0..n {
        ptr::write_volatile(p.add(i), 0);
    }
    core::sync::atomic::compiler_fence(core::sync::atomic::Ordering::SeqCst);
}

#[inline(always)]
fn f1(x: u32, y: u32, z: u32) -> u32 {
    z ^ (x & (y ^ z))
}
#[inline(always)]
fn f2(x: u32, y: u32, z: u32) -> u32 {
    f1(z, x, y)
}
#[inline(always)]
fn f3(x: u32, y: u32, z: u32) -> u32 {
    x ^ y ^ z
}
#[inline(always)]
fn f4(x: u32, y: u32, z: u32) -> u32 {
    y ^ (x | !z)
}

macro_rules! md5step {
    ($f:ident, $w:ident, $x:ident, $y:ident, $z:ident, $in:expr, $k:expr, $s:expr) => {
        $w = $w.wrapping_add($f($x, $y, $z).wrapping_add($in.wrapping_add($k)));
        $w = $w.rotate_left($s).wrapping_add($x);
    };
}

/// Process one 64-byte block read from `data`.
unsafe fn md5_block(state: &mut md5_block_state, data: *const u8) {
    let mut bytes = [0u8; MD5_BLOCK_SIZE];
    ptr::copy_nonoverlapping(data, bytes.as_mut_ptr(), MD5_BLOCK_SIZE);
    let mut inp = [0u32; MD5_BLOCK_WORDS];
    for (i, w) in inp.iter_mut().enumerate() {
        *w = u32::from_le_bytes([
            bytes[4 * i],
            bytes[4 * i + 1],
            bytes[4 * i + 2],
            bytes[4 * i + 3],
        ]);
    }

    let mut a = state.h[0];
    let mut b = state.h[1];
    let mut c = state.h[2];
    let mut d = state.h[3];

    md5step!(f1, a, b, c, d, inp[0], 0xd76aa478u32, 7);
    md5step!(f1, d, a, b, c, inp[1], 0xe8c7b756u32, 12);
    md5step!(f1, c, d, a, b, inp[2], 0x242070dbu32, 17);
    md5step!(f1, b, c, d, a, inp[3], 0xc1bdceeeu32, 22);
    md5step!(f1, a, b, c, d, inp[4], 0xf57c0fafu32, 7);
    md5step!(f1, d, a, b, c, inp[5], 0x4787c62au32, 12);
    md5step!(f1, c, d, a, b, inp[6], 0xa8304613u32, 17);
    md5step!(f1, b, c, d, a, inp[7], 0xfd469501u32, 22);
    md5step!(f1, a, b, c, d, inp[8], 0x698098d8u32, 7);
    md5step!(f1, d, a, b, c, inp[9], 0x8b44f7afu32, 12);
    md5step!(f1, c, d, a, b, inp[10], 0xffff5bb1u32, 17);
    md5step!(f1, b, c, d, a, inp[11], 0x895cd7beu32, 22);
    md5step!(f1, a, b, c, d, inp[12], 0x6b901122u32, 7);
    md5step!(f1, d, a, b, c, inp[13], 0xfd987193u32, 12);
    md5step!(f1, c, d, a, b, inp[14], 0xa679438eu32, 17);
    md5step!(f1, b, c, d, a, inp[15], 0x49b40821u32, 22);

    md5step!(f2, a, b, c, d, inp[1], 0xf61e2562u32, 5);
    md5step!(f2, d, a, b, c, inp[6], 0xc040b340u32, 9);
    md5step!(f2, c, d, a, b, inp[11], 0x265e5a51u32, 14);
    md5step!(f2, b, c, d, a, inp[0], 0xe9b6c7aau32, 20);
    md5step!(f2, a, b, c, d, inp[5], 0xd62f105du32, 5);
    md5step!(f2, d, a, b, c, inp[10], 0x02441453u32, 9);
    md5step!(f2, c, d, a, b, inp[15], 0xd8a1e681u32, 14);
    md5step!(f2, b, c, d, a, inp[4], 0xe7d3fbc8u32, 20);
    md5step!(f2, a, b, c, d, inp[9], 0x21e1cde6u32, 5);
    md5step!(f2, d, a, b, c, inp[14], 0xc33707d6u32, 9);
    md5step!(f2, c, d, a, b, inp[3], 0xf4d50d87u32, 14);
    md5step!(f2, b, c, d, a, inp[8], 0x455a14edu32, 20);
    md5step!(f2, a, b, c, d, inp[13], 0xa9e3e905u32, 5);
    md5step!(f2, d, a, b, c, inp[2], 0xfcefa3f8u32, 9);
    md5step!(f2, c, d, a, b, inp[7], 0x676f02d9u32, 14);
    md5step!(f2, b, c, d, a, inp[12], 0x8d2a4c8au32, 20);

    md5step!(f3, a, b, c, d, inp[5], 0xfffa3942u32, 4);
    md5step!(f3, d, a, b, c, inp[8], 0x8771f681u32, 11);
    md5step!(f3, c, d, a, b, inp[11], 0x6d9d6122u32, 16);
    md5step!(f3, b, c, d, a, inp[14], 0xfde5380cu32, 23);
    md5step!(f3, a, b, c, d, inp[1], 0xa4beea44u32, 4);
    md5step!(f3, d, a, b, c, inp[4], 0x4bdecfa9u32, 11);
    md5step!(f3, c, d, a, b, inp[7], 0xf6bb4b60u32, 16);
    md5step!(f3, b, c, d, a, inp[10], 0xbebfbc70u32, 23);
    md5step!(f3, a, b, c, d, inp[13], 0x289b7ec6u32, 4);
    md5step!(f3, d, a, b, c, inp[0], 0xeaa127fau32, 11);
    md5step!(f3, c, d, a, b, inp[3], 0xd4ef3085u32, 16);
    md5step!(f3, b, c, d, a, inp[6], 0x04881d05u32, 23);
    md5step!(f3, a, b, c, d, inp[9], 0xd9d4d039u32, 4);
    md5step!(f3, d, a, b, c, inp[12], 0xe6db99e5u32, 11);
    md5step!(f3, c, d, a, b, inp[15], 0x1fa27cf8u32, 16);
    md5step!(f3, b, c, d, a, inp[2], 0xc4ac5665u32, 23);

    md5step!(f4, a, b, c, d, inp[0], 0xf4292244u32, 6);
    md5step!(f4, d, a, b, c, inp[7], 0x432aff97u32, 10);
    md5step!(f4, c, d, a, b, inp[14], 0xab9423a7u32, 15);
    md5step!(f4, b, c, d, a, inp[5], 0xfc93a039u32, 21);
    md5step!(f4, a, b, c, d, inp[12], 0x655b59c3u32, 6);
    md5step!(f4, d, a, b, c, inp[3], 0x8f0ccc92u32, 10);
    md5step!(f4, c, d, a, b, inp[10], 0xffeff47du32, 15);
    md5step!(f4, b, c, d, a, inp[1], 0x85845dd1u32, 21);
    md5step!(f4, a, b, c, d, inp[8], 0x6fa87e4fu32, 6);
    md5step!(f4, d, a, b, c, inp[15], 0xfe2ce6e0u32, 10);
    md5step!(f4, c, d, a, b, inp[6], 0xa3014314u32, 15);
    md5step!(f4, b, c, d, a, inp[13], 0x4e0811a1u32, 21);
    md5step!(f4, a, b, c, d, inp[4], 0xf7537e82u32, 6);
    md5step!(f4, d, a, b, c, inp[11], 0xbd3af235u32, 10);
    md5step!(f4, c, d, a, b, inp[2], 0x2ad7d2bbu32, 15);
    md5step!(f4, b, c, d, a, inp[9], 0xeb86d391u32, 21);

    state.h[0] = state.h[0].wrapping_add(a);
    state.h[1] = state.h[1].wrapping_add(b);
    state.h[2] = state.h[2].wrapping_add(c);
    state.h[3] = state.h[3].wrapping_add(d);
}

/// Process `nblocks` blocks (do/while semantics, as in C).
unsafe fn md5_blocks(state: &mut md5_block_state, mut data: *const u8, mut nblocks: usize) {
    loop {
        md5_block(state, data);
        data = data.wrapping_add(MD5_BLOCK_SIZE);
        nblocks = nblocks.wrapping_sub(1);
        if nblocks == 0 {
            break;
        }
    }
}

/// cpu_to_le32_array() is a no-op on little-endian; return the raw bytes of h.
fn hash_bytes(state: &md5_block_state) -> [u8; MD5_DIGEST_SIZE] {
    let mut out = [0u8; MD5_DIGEST_SIZE];
    for i in 0..MD5_HASH_WORDS {
        out[4 * i..4 * i + 4].copy_from_slice(&state.h[i].to_ne_bytes());
    }
    out
}

#[no_mangle]
pub extern "C" fn md5_init(ctx: *mut md5_ctx) {
    unsafe {
        (*ctx).state = MD5_IV;
        (*ctx).bytecount = 0;
    }
}

#[no_mangle]
pub extern "C" fn md5_update(ctx: *mut md5_ctx, data: *const u8, len: usize) {
    unsafe {
        let ctx = &mut *ctx;
        let mut data = data;
        let mut len = len;
        let mut partial = (ctx.bytecount % MD5_BLOCK_SIZE as u64) as usize;

        ctx.bytecount = ctx.bytecount.wrapping_add(len as u64);

        if partial.wrapping_add(len) >= MD5_BLOCK_SIZE {
            if partial != 0 {
                let l = MD5_BLOCK_SIZE - partial;
                ptr::copy_nonoverlapping(data, ctx.buf.0.as_mut_ptr().add(partial), l);
                data = data.wrapping_add(l);
                len = len.wrapping_sub(l);

                md5_blocks(&mut ctx.state, ctx.buf.0.as_ptr(), 1);
            }

            let nblocks = len / MD5_BLOCK_SIZE;
            len %= MD5_BLOCK_SIZE;

            if nblocks != 0 {
                md5_blocks(&mut ctx.state, data, nblocks);
                data = data.wrapping_add(nblocks.wrapping_mul(MD5_BLOCK_SIZE));
            }
            partial = 0;
        }
        if len != 0 {
            ptr::copy_nonoverlapping(data, ctx.buf.0.as_mut_ptr().add(partial), len);
        }
    }
}

/// __md5_final(): finalize the hash in `ctx` and return the digest
/// (ctx->state.h is left holding the little-endian digest, as in C).
fn md5_final_inner(ctx: &mut md5_ctx) -> [u8; MD5_DIGEST_SIZE] {
    let bitcount: u64 = ctx.bytecount.wrapping_shl(3);
    let mut partial = (ctx.bytecount % MD5_BLOCK_SIZE as u64) as usize;

    ctx.buf.0[partial] = 0x80;
    partial += 1;
    if partial > MD5_BLOCK_SIZE - 8 {
        for b in ctx.buf.0[partial..].iter_mut() {
            *b = 0;
        }
        unsafe { md5_blocks(&mut ctx.state, ctx.buf.0.as_ptr(), 1) };
        partial = 0;
    }
    for b in ctx.buf.0[partial..MD5_BLOCK_SIZE - 8].iter_mut() {
        *b = 0;
    }
    ctx.buf.0[MD5_BLOCK_SIZE - 8..].copy_from_slice(&bitcount.to_le_bytes());
    unsafe { md5_blocks(&mut ctx.state, ctx.buf.0.as_ptr(), 1) };

    hash_bytes(&ctx.state)
}

#[no_mangle]
pub extern "C" fn md5_final(ctx: *mut md5_ctx, out: *mut u8) {
    unsafe {
        let digest = md5_final_inner(&mut *ctx);
        ptr::copy_nonoverlapping(digest.as_ptr(), out, MD5_DIGEST_SIZE);
        memzero_explicit(ctx as *mut u8, size_of::<md5_ctx>());
    }
}

#[no_mangle]
pub extern "C" fn md5(data: *const u8, len: usize, out: *mut u8) {
    let mut ctx = md5_ctx {
        state: md5_block_state { h: [0; MD5_HASH_WORDS] },
        bytecount: 0,
        buf: Md5Buf([0; MD5_BLOCK_SIZE]),
    };
    md5_init(&mut ctx);
    md5_update(&mut ctx, data, len);
    md5_final(&mut ctx, out);
}

unsafe fn hmac_md5_preparekey_inner(
    istate: *mut md5_block_state,
    ostate: *mut md5_block_state,
    raw_key: *const u8,
    raw_key_len: usize,
) {
    let mut derived_key = [0u8; MD5_BLOCK_SIZE];

    if raw_key_len > MD5_BLOCK_SIZE {
        md5(raw_key, raw_key_len, derived_key.as_mut_ptr());
    } else {
        ptr::copy_nonoverlapping(raw_key, derived_key.as_mut_ptr(), raw_key_len);
    }

    // XOR of each unsigned long with REPEAT_BYTE(v) == XOR of each byte with v.
    for b in derived_key.iter_mut() {
        *b ^= HMAC_IPAD_VALUE;
    }
    *istate = MD5_IV;
    md5_blocks(&mut *istate, derived_key.as_ptr(), 1);

    for b in derived_key.iter_mut() {
        *b ^= HMAC_OPAD_VALUE ^ HMAC_IPAD_VALUE;
    }
    *ostate = MD5_IV;
    md5_blocks(&mut *ostate, derived_key.as_ptr(), 1);

    memzero_explicit(derived_key.as_mut_ptr(), MD5_BLOCK_SIZE);
}

#[no_mangle]
pub extern "C" fn hmac_md5_preparekey(key: *mut hmac_md5_key, raw_key: *const u8, raw_key_len: usize) {
    unsafe {
        hmac_md5_preparekey_inner(
            ptr::addr_of_mut!((*key).istate),
            ptr::addr_of_mut!((*key).ostate),
            raw_key,
            raw_key_len,
        );
    }
}

#[no_mangle]
pub extern "C" fn hmac_md5_init(ctx: *mut hmac_md5_ctx, key: *const hmac_md5_key) {
    unsafe {
        (*ctx).hash_ctx.state = (*key).istate;
        (*ctx).hash_ctx.bytecount = MD5_BLOCK_SIZE as u64;
        (*ctx).ostate = (*key).ostate;
    }
}

#[no_mangle]
pub extern "C" fn hmac_md5_init_usingrawkey(ctx: *mut hmac_md5_ctx, raw_key: *const u8, raw_key_len: usize) {
    unsafe {
        hmac_md5_preparekey_inner(
            ptr::addr_of_mut!((*ctx).hash_ctx.state),
            ptr::addr_of_mut!((*ctx).ostate),
            raw_key,
            raw_key_len,
        );
        (*ctx).hash_ctx.bytecount = MD5_BLOCK_SIZE as u64;
    }
}

#[inline]
fn hmac_md5_update(ctx: *mut hmac_md5_ctx, data: *const u8, data_len: usize) {
    unsafe { md5_update(ptr::addr_of_mut!((*ctx).hash_ctx), data, data_len) };
}

#[no_mangle]
pub extern "C" fn hmac_md5_final(ctx: *mut hmac_md5_ctx, out: *mut u8) {
    unsafe {
        let c = &mut *ctx;
        // Generate the padded input for the outer hash in hash_ctx.buf.
        let inner = md5_final_inner(&mut c.hash_ctx);
        c.hash_ctx.buf.0[..MD5_DIGEST_SIZE].copy_from_slice(&inner);
        for b in c.hash_ctx.buf.0[MD5_DIGEST_SIZE..].iter_mut() {
            *b = 0;
        }
        c.hash_ctx.buf.0[MD5_DIGEST_SIZE] = 0x80;
        let bits: u64 = 8 * (MD5_BLOCK_SIZE + MD5_DIGEST_SIZE) as u64;
        c.hash_ctx.buf.0[MD5_BLOCK_SIZE - 8..].copy_from_slice(&bits.to_le_bytes());

        // Compute the outer hash, which gives the HMAC value.
        md5_blocks(&mut c.ostate, c.hash_ctx.buf.0.as_ptr(), 1);
        let digest = hash_bytes(&c.ostate);
        ptr::copy_nonoverlapping(digest.as_ptr(), out, MD5_DIGEST_SIZE);

        // hmac_md5_zeroize_ctx()
        memzero_explicit(ctx as *mut u8, size_of::<hmac_md5_ctx>());
    }
}

#[no_mangle]
pub extern "C" fn hmac_md5(key: *const hmac_md5_key, data: *const u8, data_len: usize, out: *mut u8) {
    let mut ctx = hmac_md5_ctx {
        hash_ctx: md5_ctx {
            state: md5_block_state { h: [0; MD5_HASH_WORDS] },
            bytecount: 0,
            buf: Md5Buf([0; MD5_BLOCK_SIZE]),
        },
        ostate: md5_block_state { h: [0; MD5_HASH_WORDS] },
    };
    hmac_md5_init(&mut ctx, key);
    hmac_md5_update(&mut ctx, data, data_len);
    hmac_md5_final(&mut ctx, out);
}

#[no_mangle]
pub extern "C" fn hmac_md5_usingrawkey(
    raw_key: *const u8,
    raw_key_len: usize,
    data: *const u8,
    data_len: usize,
    out: *mut u8,
) {
    let mut ctx = hmac_md5_ctx {
        hash_ctx: md5_ctx {
            state: md5_block_state { h: [0; MD5_HASH_WORDS] },
            bytecount: 0,
            buf: Md5Buf([0; MD5_BLOCK_SIZE]),
        },
        ostate: md5_block_state { h: [0; MD5_HASH_WORDS] },
    };
    hmac_md5_init_usingrawkey(&mut ctx, raw_key, raw_key_len);
    hmac_md5_update(&mut ctx, data, data_len);
    hmac_md5_final(&mut ctx, out);
}
