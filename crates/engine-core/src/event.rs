



pub const EVENT_RING_CAPACITY: usize = 24;


pub const NO_MON: u8 = 0xFF;

#[derive(Clone, Copy, PartialEq, Eq, Debug, Default)]
#[repr(u8)]
pub enum EventKind {
    #[default]
    Empty = 0,
    Move = 1,
    Switch = 2,
    Faint = 3,
    StatusApplied = 4,
    BoostApplied = 5,
    Damage = 6,
    Heal = 7,
}










#[derive(Clone, Copy, PartialEq, Eq, Debug, Default)]
pub struct Event {
    pub actor: u8,
    pub kind: EventKind,
    pub target: u8,
    pub subject: u16,
    pub outcome: i16,
}

#[derive(Clone, Copy, Debug)]
pub struct EventRing {
    events: [Event; EVENT_RING_CAPACITY],

    next: u8,

    len: u8,
}

impl Default for EventRing {
    fn default() -> Self {
        EventRing { events: [Event::default(); EVENT_RING_CAPACITY], next: 0, len: 0 }
    }
}

impl EventRing {
    pub fn push(&mut self, event: Event) {
        self.events[self.next as usize] = event;
        self.next = (self.next + 1) % EVENT_RING_CAPACITY as u8;
        if (self.len as usize) < EVENT_RING_CAPACITY {
            self.len += 1;
        }
    }


    pub fn cursor(&self) -> u8 {
        self.next
    }


    pub fn since_mut(&mut self, cursor: u8) -> impl Iterator<Item = &mut Event> {
        let n = (self.next as usize + EVENT_RING_CAPACITY - cursor as usize) % EVENT_RING_CAPACITY;
        let start = cursor as usize;
        let (head, tail) = self.events.split_at_mut(start);
        tail.iter_mut().chain(head.iter_mut()).take(n)
    }

    pub fn len(&self) -> usize {
        self.len as usize
    }


    pub fn iter(&self) -> impl Iterator<Item = &Event> {
        let start = if (self.len as usize) < EVENT_RING_CAPACITY { 0 } else { self.next as usize };
        let len = self.len as usize;
        (0..len).map(move |i| &self.events[(start + i) % EVENT_RING_CAPACITY])
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn event(n: u16) -> Event {
        Event { actor: 0, kind: EventKind::Move, target: 1, subject: n, outcome: 0 }
    }

    #[test]
    fn push_and_iterate_in_order() {
        let mut ring = EventRing::default();
        ring.push(event(1));
        ring.push(event(2));
        ring.push(event(3));
        let got: Vec<u16> = ring.iter().map(|e| e.subject).collect();
        assert_eq!(got, vec![1, 2, 3]);
    }

    #[test]
    fn since_mut_sees_only_newer_events_across_the_wrap() {
        let mut ring = EventRing::default();
        for i in 0..(EVENT_RING_CAPACITY as u16 - 2) {
            ring.push(event(i));
        }
        let cursor = ring.cursor();
        for i in 100..105 {
            ring.push(event(i));
        }
        let got: Vec<u16> = ring.since_mut(cursor).map(|e| e.subject).collect();
        assert_eq!(got, vec![100, 101, 102, 103, 104]);
        ring.since_mut(cursor).for_each(|e| e.target = 7);
        assert!(ring.iter().filter(|e| e.subject >= 100).all(|e| e.target == 7));
        assert_eq!(ring.since_mut(ring.cursor()).count(), 0);
    }

    #[test]
    fn wraps_and_drops_oldest() {
        let mut ring = EventRing::default();
        for i in 0..(EVENT_RING_CAPACITY as u16 + 5) {
            ring.push(event(i));
        }
        assert_eq!(ring.len(), EVENT_RING_CAPACITY);
        let got: Vec<u16> = ring.iter().map(|e| e.subject).collect();

        assert_eq!(got[0], 5);
        assert_eq!(*got.last().unwrap(), EVENT_RING_CAPACITY as u16 + 4);
    }
}
