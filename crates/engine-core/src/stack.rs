





use core::ops::{Deref, DerefMut};

#[derive(Clone, Copy, Debug)]
pub struct StackVec<T: Copy + Default, const N: usize> {
    items: [T; N],
    len: usize,
}

impl<T: Copy + Default, const N: usize> Default for StackVec<T, N> {
    fn default() -> Self {
        Self::new()
    }
}

impl<T: Copy + Default, const N: usize> StackVec<T, N> {
    #[inline]
    pub fn new() -> Self {
        Self { items: [T::default(); N], len: 0 }
    }

    #[inline]
    pub fn push(&mut self, x: T) {
        assert!(self.len < N, "StackVec capacity {N} exceeded");
        self.items[self.len] = x;
        self.len += 1;
    }

    #[inline]
    pub fn pop(&mut self) -> Option<T> {
        if self.len == 0 {
            return None;
        }
        self.len -= 1;
        Some(self.items[self.len])
    }

    #[inline]
    pub fn clear(&mut self) {
        self.len = 0;
    }


    pub fn insert(&mut self, at: usize, x: T) {
        assert!(at <= self.len, "StackVec insert index {at} past len {}", self.len);
        self.push(x);
        self.items[at..self.len].rotate_right(1);
    }


    pub fn remove(&mut self, at: usize) -> T {
        assert!(at < self.len, "StackVec remove index {at} past len {}", self.len);
        let x = self.items[at];
        self.items[at..self.len].rotate_left(1);
        self.len -= 1;
        x
    }


    pub fn retain(&mut self, mut keep: impl FnMut(&T) -> bool) {
        let mut w = 0;
        for r in 0..self.len {
            if keep(&self.items[r]) {
                self.items[w] = self.items[r];
                w += 1;
            }
        }
        self.len = w;
    }

    #[inline]
    pub fn truncate(&mut self, len: usize) {
        self.len = self.len.min(len);
    }
}

impl<T: Copy + Default, const N: usize> Deref for StackVec<T, N> {
    type Target = [T];
    #[inline]
    fn deref(&self) -> &[T] {
        &self.items[..self.len]
    }
}

impl<T: Copy + Default, const N: usize> DerefMut for StackVec<T, N> {
    #[inline]
    fn deref_mut(&mut self) -> &mut [T] {
        &mut self.items[..self.len]
    }
}

impl<T: Copy + Default, const N: usize> FromIterator<T> for StackVec<T, N> {
    fn from_iter<I: IntoIterator<Item = T>>(iter: I) -> Self {
        let mut v = Self::new();
        for x in iter {
            v.push(x);
        }
        v
    }
}

impl<T: Copy + Default, const N: usize> Extend<T> for StackVec<T, N> {
    fn extend<I: IntoIterator<Item = T>>(&mut self, iter: I) {
        for x in iter {
            self.push(x);
        }
    }
}


impl<T: Copy + Default, const N: usize> IntoIterator for StackVec<T, N> {
    type Item = T;
    type IntoIter = core::iter::Take<core::array::IntoIter<T, N>>;
    fn into_iter(self) -> Self::IntoIter {
        self.items.into_iter().take(self.len)
    }
}

impl<'a, T: Copy + Default, const N: usize> IntoIterator for &'a StackVec<T, N> {
    type Item = &'a T;
    type IntoIter = core::slice::Iter<'a, T>;
    fn into_iter(self) -> Self::IntoIter {
        self.iter()
    }
}

#[cfg(test)]
mod tests {
    use super::StackVec;

    #[test]
    fn behaves_like_a_vec() {
        let mut v: StackVec<u8, 6> = StackVec::new();
        v.extend([3, 1, 2]);
        v.insert(1, 9);
        assert_eq!(&*v, &[3, 9, 1, 2]);
        assert_eq!(v.remove(0), 3);
        v.sort();
        assert_eq!(&*v, &[1, 2, 9]);
        v.retain(|&x| x != 2);
        assert_eq!(v.into_iter().collect::<Vec<_>>(), vec![1, 9]);
        let w: StackVec<u8, 6> = (0..4).collect();
        assert_eq!(w.len(), 4);
    }

    #[test]
    #[should_panic(expected = "capacity")]
    fn overflow_is_loud() {
        let mut v: StackVec<u8, 2> = StackVec::new();
        v.extend([1, 2, 3]);
    }
}
