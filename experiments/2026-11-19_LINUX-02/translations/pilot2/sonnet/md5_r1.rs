use core::ffi::c_ulong;
use core::ptr;

const MD5_DIGEST_SIZE: usize = 16;
const MD5_BLOCK_SIZE: usize = 64;
const MD5_BLOCK_WORDS: usize = 16;
const MD5_HASH_WORDS: usize = 4;

const MD5_H0: u32 = 0x67452301;
const MD5_H1: u32 = 0xefcdab89;
const MD5_H2: u32 = 0x98badcfe;
const MD5_H3: u32 = 0x10325476;

const HMAC_IPAD_VALUE: u8 = 0x36;
const HMAC_OPAD_VALUE: u8 = 0x5c;

#[repr(C)]
#[derive(Clone, Copy)]
pub struct Md5State {
    pub hash: [u32; MD5_HASH_WORDS],
    pub byte_count: u64,
    pub block: [u32; MD5_BLOCK_WORDS],
}

#[repr(C)]
#[derive(Clone, Copy)]
pub struct Md5BlockState {
    pub h: [u32; MD5_HASH_WORDS],
}

#[repr(C, align(8))]
#[derive(Clone, Copy)]
pub struct Md5Buf(pub [u8; MD5_BLOCK_SIZE]);

#[repr(C)]
#[derive(Clone, Copy)]
pub struct Md5Ctx {
    pub state: Md5BlockState,
    pub bytecount: u64,
    pub buf: Md5Buf,
}

#[repr(C)]
#[derive(Clone, Copy)]
pub struct HmacMd5Key {
    pub istate: Md5BlockState,
    pub ostate: Md5BlockState,
}

#[repr(C)]
#[derive(Clone, Copy)]
pub struct HmacMd5Ctx {
    pub hash_ctx: Md5Ctx,
    pub ostate: Md5BlockState,
}

const _: () = {
    assert!(core::mem::size_of::<Md5Ctx>() == 88);
    assert!(core::mem::align_of::<Md5Ctx>() == 8);
    assert!(core::mem::size_of::<HmacMd5Ctx>() == 104);
    assert!(core::mem::size_of::<HmacMd5Key>() == 32);
    assert!(core::mem::size_of::<Md5State>() == 88);
};

static MD5_IV: Md5BlockState = Md5BlockState {
    h: [MD5_H0, MD5_H1, MD5_H2, MD5_H3],
};

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

/// Zeroize memory in a way that cannot be optimized away.
unsafe fn memzero_explicit(p: *mut u8, n: usize) {
    let mut i = 0;
    while i < n {
        ptr::write_volatile(p.add(i), 0);
        i += 1;
    }
    core::sync::atomic::compiler_fence(core::sync::atomic::Ordering::SeqCst);
}

unsafe fn md5_block(state: *mut Md5BlockState, data: *const u8) {
    let mut inp = [0u32; MD5_BLOCK_WORDS];
    ptr::copy_nonoverlapping(data, inp.as_mut_ptr() as *mut u8, MD5_BLOCK_SIZE);
    // le32_to_cpu_array: no-op on little-endian.

    let h = ptr::addr_of_mut!((*state).h) as *mut u32;
    let mut a = *h;
    let mut b = *h.add(1);
    let mut c = *h.add(2);
    let mut d = *h.add(3);

    macro_rules! step {
        ($f:ident, $w:ident, $x:ident, $y:ident, $z:ident, $i:expr, $k:expr, $s:expr) => {
            $w = $w.wrapping_add($f($x, $y, $z).wrapping_add(inp[$i].wrapping_add($k)));
            $w = $w.rotate_left($s).wrapping_add($x);
        };
    }

    step!(f1, a, b, c, d, 0, 0xd76aa478u32, 7);
    step!(f1, d, a, b, c, 1, 0xe8c7b756u32, 12);
    step!(f1, c, d, a, b, 2, 0x242070dbu32, 17);
    step!(f1, b, c, d, a, 3, 0xc1bdceeeu32, 22);
    step!(f1, a, b, c, d, 4, 0xf57c0fafu32, 7);
    step!(f1, d, a, b, c, 5, 0x4787c62au32, 12);
    step!(f1, c, d, a, b, 6, 0xa8304613u32, 17);
    step!(f1, b, c, d, a, 7, 0xfd469501u32, 22);
    step!(f1, a, b, c, d, 8, 0x698098d8u32, 7);
    step!(f1, d, a, b, c, 9, 0x8b44f7afu32, 12);
    step!(f1, c, d, a, b, 10, 0xffff5bb1u32, 17);
    step!(f1, b, c, d, a, 11, 0x895cd7beu32, 22);
    step!(f1, a, b, c, d, 12, 0x6b901122u32, 7);
    step!(f1, d, a, b, c, 13, 0xfd987193u32, 12);
    step!(f1, c, d, a, b, 14, 0xa679438eu32, 17);
    step!(f1, b, c, d, a, 15, 0x49b40821u32, 22);

    step!(f2, a, b, c, d, 1, 0xf61e2562u32, 5);
    step!(f2, d, a, b, c, 6, 0xc040b340u32, 9);
    step!(f2, c, d, a, b, 11, 0x265e5a51u32, 14);
    step!(f2, b, c, d, a, 0, 0xe9b6c7aau32, 20);
    step!(f2, a, b, c, d, 5, 0xd62f105du32, 5);
    step!(f2, d, a, b, c, 10, 0x02441453u32, 9);
    step!(f2, c, d, a, b, 15, 0xd8a1e681u32, 14);
    step!(f2, b, c, d, a, 4, 0xe7d3fbc8u32, 20);
    step!(f2, a, b, c, d, 9, 0x21e1cde6u32, 5);
    step!(f2, d, a, b, c, 14, 0xc33707d6u32, 9);
    step!(f2, c, d, a, b, 3, 0xf4d50d87u32, 14);
    step!(f2, b, c, d, a, 8, 0x455a14edu32, 20);
    step!(f2, a, b, c, d, 13, 0xa9e3e905u32, 5);
    step!(f2, d, a, b, c, 2, 0xfcefa3f8u32, 9);
    step!(f2, c, d, a, b, 7, 0x676f02d9u32, 14);
    step!(f2, b, c, d, a, 12, 0x8d2a4c8au32, 20);

    step!(f3, a, b, c, d, 5, 0xfffa3942u32, 4);
    step!(f3, d, a, b, c, 8, 0x8771f681u32, 11);
    step!(f3, c, d, a, b, 11, 0x6d9d6122u32, 16);
    step!(f3, b, c, d, a, 14, 0xfde5380cu32, 23);
    step!(f3, a, b, c, d, 1, 0xa4beea44u32, 4);
    step!(f3, d, a, b, c, 4, 0x4bdecfa9u32, 11);
    step!(f3, c, d, a, b, 7, 0xf6bb4b60u32, 16);
    step!(f3, b, c, d, a, 10, 0xbebfbc70u32, 23);
    step!(f3, a, b, c, d, 13, 0x289b7ec6u32, 4);
    step!(f3, d, a, b, c, 0, 0xeaa127fau32, 11);
    step!(f3, c, d, a, b, 3, 0xd4ef3085u32, 16);
    step!(f3, b, c, d, a, 6, 0x04881d05u32, 23);
    step!(f3, a, b, c, d, 9, 0xd9d4d039u32, 4);
    step!(f3, d, a, b, c, 12, 0xe6db99e5u32, 11);
    step!(f3, c, d, a, b, 15, 0x1fa27cf8u32, 16);
    step!(f3, b, c, d, a, 2, 0xc4ac5665u32, 23);

    step!(f4, a, b, c, d, 0, 0xf4292244u32, 6);
    step!(f4, d, a, b, c, 7, 0x432aff97u32, 10);
    step!(f4, c, d, a, b, 14, 0xab9423a7u32, 15);
    step!(f4, b, c, d, a, 5, 0xfc93a039u32, 21);
    step!(f4, a, b, c, d, 12, 0x655b59c3u32, 6);
    step!(f4, d, a, b, c, 3, 0x8f0ccc92u32, 10);
    step!(f4, c, d, a, b, 10, 0xffeff47du32, 15);
    step!(f4, b, c, d, a, 1, 0x85845dd1u32, 21);
    step!(f4, a, b, c, d, 8, 0x6fa87e4fu32, 6);
    step!(f4, d, a, b, c, 15, 0xfe2ce6e0u32, 10);
    step!(f4, c, d, a, b, 6, 0xa3014314u32, 15);
    step!(f4, b, c, d, a, 13, 0x4e0811a1u32, 21);
    step!(f4, a, b, c, d, 4, 0xf7537e82u32, 6);
    step!(f4, d, a, b, c, 11, 0xbd3af235u32, 10);
    step!(f4, c, d, a, b, 2, 0x2ad7d2bbu32, 15);
    step!(f4, b, c, d, a, 9, 0xeb86d391u32, 21);

    *h = (*h).wrapping_add(a);
    *h.add(1) = (*h.add(1)).wrapping_add(b);
    *h.add(2) = (*h.add(2)).wrapping_add(c);
    *h.add(3) = (*h.add(3)).wrapping_add(d);
}

unsafe fn md5_blocks(state: *mut Md5BlockState, mut data: *const u8, mut nblocks: usize) {
    loop {
        md5_block(state, data);
        data = data.wrapping_add(MD5_BLOCK_SIZE);
        nblocks = nblocks.wrapping_sub(1);
        if nblocks == 0 {
            break;
        }
    }
}

#[no_mangle]
pub extern "C" fn md5_init(ctx: *mut Md5Ctx) {
    unsafe {
        (*ctx).state = MD5_IV;
        (*ctx).bytecount = 0;
    }
}

#[no_mangle]
pub extern "C" fn md5_update(ctx: *mut Md5Ctx, data: *const u8, len: usize) {
    unsafe {
        let buf = ptr::addr_of_mut!((*ctx).buf) as *mut u8;
        let state = ptr::addr_of_mut!((*ctx).state);
        let mut data = data;
        let mut len = len;
        let mut partial = ((*ctx).bytecount % MD5_BLOCK_SIZE as u64) as usize;

        (*ctx).bytecount = (*ctx).bytecount.wrapping_add(len as u64);

        if partial.wrapping_add(len) >= MD5_BLOCK_SIZE {
            if partial != 0 {
                let l = MD5_BLOCK_SIZE - partial;

                ptr::copy_nonoverlapping(data, buf.add(partial), l);
                data = data.wrapping_add(l);
                len = len.wrapping_sub(l);

                md5_blocks(state, buf, 1);
            }

            let nblocks = len / MD5_BLOCK_SIZE;
            len %= MD5_BLOCK_SIZE;

            if nblocks != 0 {
                md5_blocks(state, data, nblocks);
                data = data.wrapping_add(nblocks.wrapping_mul(MD5_BLOCK_SIZE));
            }
            partial = 0;
        }
        if len != 0 {
            ptr::copy_nonoverlapping(data, buf.add(partial), len);
        }
    }
}

unsafe fn md5_final_inner(ctx: *mut Md5Ctx, out: *mut u8) {
    let buf = ptr::addr_of_mut!((*ctx).buf) as *mut u8;
    let state = ptr::addr_of_mut!((*ctx).state);
    let bitcount: u64 = (*ctx).bytecount << 3;
    let mut partial = ((*ctx).bytecount % MD5_BLOCK_SIZE as u64) as usize;

    *buf.add(partial) = 0x80;
    partial += 1;
    if partial > MD5_BLOCK_SIZE - 8 {
        ptr::write_bytes(buf.add(partial), 0, MD5_BLOCK_SIZE - partial);
        md5_blocks(state, buf, 1);
        partial = 0;
    }
    ptr::write_bytes(buf.add(partial), 0, MD5_BLOCK_SIZE - 8 - partial);
    ptr::write_unaligned(buf.add(MD5_BLOCK_SIZE - 8) as *mut u64, bitcount.to_le());
    md5_blocks(state, buf, 1);

    // cpu_to_le32_array: no-op on little-endian.
    ptr::copy(
        ptr::addr_of!((*state).h) as *const u8,
        out,
        MD5_DIGEST_SIZE,
    );
}

#[no_mangle]
pub extern "C" fn md5_final(ctx: *mut Md5Ctx, out: *mut u8) {
    unsafe {
        md5_final_inner(ctx, out);
        memzero_explicit(ctx as *mut u8, core::mem::size_of::<Md5Ctx>());
    }
}

#[no_mangle]
pub extern "C" fn md5(data: *const u8, len: usize, out: *mut u8) {
    let mut ctx = Md5Ctx {
        state: Md5BlockState { h: [0; MD5_HASH_WORDS] },
        bytecount: 0,
        buf: Md5Buf([0; MD5_BLOCK_SIZE]),
    };
    let p: *mut Md5Ctx = &mut ctx;
    md5_init(p);
    md5_update(p, data, len);
    md5_final(p, out);
}

const fn repeat_byte(x: u8) -> c_ulong {
    (!0 as c_ulong / 0xff) * (x as c_ulong)
}

unsafe fn hmac_md5_preparekey_inner(
    istate: *mut Md5BlockState,
    ostate: *mut Md5BlockState,
    raw_key: *const u8,
    raw_key_len: usize,
) {
    let mut w: [c_ulong; MD5_BLOCK_SIZE / core::mem::size_of::<c_ulong>()] =
        [0; MD5_BLOCK_SIZE / core::mem::size_of::<c_ulong>()];
    let b = w.as_mut_ptr() as *mut u8;

    if raw_key_len > MD5_BLOCK_SIZE {
        md5(raw_key, raw_key_len, b);
    } else {
        ptr::copy_nonoverlapping(raw_key, b, raw_key_len);
    }

    let n = w.len();
    let mut i = 0;
    while i < n {
        let p = (b as *mut c_ulong).add(i);
        *p ^= repeat_byte(HMAC_IPAD_VALUE);
        i += 1;
    }
    *istate = MD5_IV;
    md5_blocks(istate, b, 1);

    let mut i = 0;
    while i < n {
        let p = (b as *mut c_ulong).add(i);
        *p ^= repeat_byte(HMAC_OPAD_VALUE ^ HMAC_IPAD_VALUE);
        i += 1;
    }
    *ostate = MD5_IV;
    md5_blocks(ostate, b, 1);

    memzero_explicit(b, MD5_BLOCK_SIZE);
}

#[no_mangle]
pub extern "C" fn hmac_md5_preparekey(key: *mut HmacMd5Key, raw_key: *const u8, raw_key_len: usize) {
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
pub extern "C" fn hmac_md5_init(ctx: *mut HmacMd5Ctx, key: *const HmacMd5Key) {
    unsafe {
        (*ctx).hash_ctx.state = (*key).istate;
        (*ctx).hash_ctx.bytecount = MD5_BLOCK_SIZE as u64;
        (*ctx).ostate = (*key).ostate;
    }
}

#[no_mangle]
pub extern "C" fn hmac_md5_init_usingrawkey(
    ctx: *mut HmacMd5Ctx,
    raw_key: *const u8,
    raw_key_len: usize,
) {
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

unsafe fn hmac_md5_update(ctx: *mut HmacMd5Ctx, data: *const u8, data_len: usize) {
    md5_update(ptr::addr_of_mut!((*ctx).hash_ctx), data, data_len);
}

#[no_mangle]
pub extern "C" fn hmac_md5_final(ctx: *mut HmacMd5Ctx, out: *mut u8) {
    unsafe {
        let hctx = ptr::addr_of_mut!((*ctx).hash_ctx);
        let buf = ptr::addr_of_mut!((*ctx).hash_ctx.buf) as *mut u8;
        let ostate = ptr::addr_of_mut!((*ctx).ostate);

        // Generate the padded input for the outer hash in ctx->hash_ctx.buf.
        md5_final_inner(hctx, buf);
        ptr::write_bytes(buf.add(MD5_DIGEST_SIZE), 0, MD5_BLOCK_SIZE - MD5_DIGEST_SIZE);
        *buf.add(MD5_DIGEST_SIZE) = 0x80;
        let bits: u64 = 8 * (MD5_BLOCK_SIZE + MD5_DIGEST_SIZE) as u64;
        ptr::write_unaligned(buf.add(MD5_BLOCK_SIZE - 8) as *mut u64, bits.to_le());

        // Compute the outer hash, which gives the HMAC value.
        md5_blocks(ostate, buf, 1);
        // cpu_to_le32_array: no-op on little-endian.
        ptr::copy(
            ptr::addr_of!((*ostate).h) as *const u8,
            out,
            MD5_DIGEST_SIZE,
        );

        memzero_explicit(ctx as *mut u8, core::mem::size_of::<HmacMd5Ctx>());
    }
}

fn zeroed_hmac_ctx() -> HmacMd5Ctx {
    HmacMd5Ctx {
        hash_ctx: Md5Ctx {
            state: Md5BlockState { h: [0; MD5_HASH_WORDS] },
            bytecount: 0,
            buf: Md5Buf([0; MD5_BLOCK_SIZE]),
        },
        ostate: Md5BlockState { h: [0; MD5_HASH_WORDS] },
    }
}

#[no_mangle]
pub extern "C" fn hmac_md5(
    key: *const HmacMd5Key,
    data: *const u8,
    data_len: usize,
    out: *mut u8,
) {
    let mut ctx = zeroed_hmac_ctx();
    let p: *mut HmacMd5Ctx = &mut ctx;
    hmac_md5_init(p, key);
    unsafe { hmac_md5_update(p, data, data_len) };
    hmac_md5_final(p, out);
}

#[no_mangle]
pub extern "C" fn hmac_md5_usingrawkey(
    raw_key: *const u8,
    raw_key_len: usize,
    data: *const u8,
    data_len: usize,
    out: *mut u8,
) {
    let mut ctx = zeroed_hmac_ctx();
    let p: *mut HmacMd5Ctx = &mut ctx;
    hmac_md5_init_usingrawkey(p, raw_key, raw_key_len);
    unsafe { hmac_md5_update(p, data, data_len) };
    hmac_md5_final(p, out);
}
