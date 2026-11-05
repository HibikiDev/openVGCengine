






#[cfg(feature = "alloc-count")]
mod imp {
    use std::alloc::{GlobalAlloc, Layout, System};
    use std::cell::Cell;
    use std::collections::BTreeMap;
    use std::sync::atomic::{AtomicBool, AtomicU64, Ordering::Relaxed};
    use std::sync::Mutex;

    pub const KINDS: [&str; 4] = ["step", "obs", "masks", "reset"];
    pub static COUNTS: [AtomicU64; 4] = [AtomicU64::new(0), AtomicU64::new(0), AtomicU64::new(0), AtomicU64::new(0)];
    pub static CALLS: [AtomicU64; 4] = [AtomicU64::new(0), AtomicU64::new(0), AtomicU64::new(0), AtomicU64::new(0)];
    pub static TRACE: AtomicBool = AtomicBool::new(false);
    pub static SITES: Mutex<BTreeMap<String, u64>> = Mutex::new(BTreeMap::new());

    thread_local! {

        pub static KIND: Cell<u8> = const { Cell::new(0) };

        static BUSY: Cell<bool> = const { Cell::new(false) };
    }

    fn note() {
        let k = KIND.with(|c| c.get());
        if k == 0 || BUSY.with(|b| b.get()) {
            return;
        }
        COUNTS[(k - 1) as usize].fetch_add(1, Relaxed);
        if TRACE.load(Relaxed) {
            BUSY.with(|b| b.set(true));
            let bt = std::backtrace::Backtrace::force_capture().to_string();
            let site = first_engine_frame(&bt);
            if let Ok(mut m) = SITES.lock() {
                *m.entry(format!("{} {site}", KINDS[(k - 1) as usize])).or_insert(0) += 1;
            }
            BUSY.with(|b| b.set(false));
        }
    }


    fn first_engine_frame(bt: &str) -> String {
        let lines: Vec<&str> = bt.lines().collect();
        for (i, l) in lines.iter().enumerate() {
            let t = l.trim();
            if t.starts_with("at ") && (t.contains("engine-core") || t.contains("engine-obs") || t.contains("engine-data")) {
                let path = t[3..].rsplit(['/', '\\']).next().unwrap_or(t);
                let func = if i > 0 { lines[i - 1].trim().splitn(2, ": ").nth(1).unwrap_or("?") } else { "?" };
                let func = func.rsplit("::").take(2).collect::<Vec<_>>().into_iter().rev().collect::<Vec<_>>().join("::");
                return format!("{func} ({path})");
            }
        }

        let funcs: Vec<&str> = lines.iter().map(|l| l.trim()).filter(|t| t.contains("engine_core") || t.contains("engine_obs")).take(2).collect();
        if !funcs.is_empty() {
            return funcs.join(" <- ");
        }
        format!("(no engine frame) {}", lines.iter().take(12).map(|l| l.trim()).collect::<Vec<_>>().join(" | "))
    }

    pub struct Counting;

    unsafe impl GlobalAlloc for Counting {
        unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
            note();
            unsafe { System.alloc(layout) }
        }
        unsafe fn alloc_zeroed(&self, layout: Layout) -> *mut u8 {
            note();
            unsafe { System.alloc_zeroed(layout) }
        }
        unsafe fn realloc(&self, ptr: *mut u8, layout: Layout, new_size: usize) -> *mut u8 {
            note();
            unsafe { System.realloc(ptr, layout, new_size) }
        }
        unsafe fn dealloc(&self, ptr: *mut u8, layout: Layout) {
            unsafe { System.dealloc(ptr, layout) }
        }
    }

    #[global_allocator]
    static ALLOC: Counting = Counting;
}

#[cfg(feature = "alloc-count")]
pub use imp::{CALLS, COUNTS, KINDS, SITES, TRACE};


#[inline(always)]
pub fn counted<R>(kind: u8, f: impl FnOnce() -> R) -> R {
    #[cfg(feature = "alloc-count")]
    {
        imp::CALLS[kind as usize].fetch_add(1, std::sync::atomic::Ordering::Relaxed);
        let prev = imp::KIND.with(|c| c.replace(kind + 1));
        let r = f();
        imp::KIND.with(|c| c.set(prev));
        r
    }
    #[cfg(not(feature = "alloc-count"))]
    {
        let _ = kind;
        f()
    }
}
