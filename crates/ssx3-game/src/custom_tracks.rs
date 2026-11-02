//! Host-owned catalog for additional Single Event courses.
//!
//! IDs here never index the guest's 17-entry TrackInfo table or its career
//! save records. Menu and race integration can look up an entry by its stable
//! string ID, then resolve its own world and race data.

use std::sync::atomic::{AtomicBool, AtomicU32, AtomicUsize, Ordering};
use std::sync::Mutex;

use ssx3_ee_rt::Cpu;

/// A selectable group of additional Single Event courses.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct CustomPeak {
    pub id: &'static str,
    pub name: &'static str,
}

/// The original SSX 3 race setup remains the authority for game mechanics.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum EventKind {
    Race,
}

/// Source disc and archive needed for a course's world assets.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum TrackSource {
    TrickyPs2 { archive: &'static str },
}

/// A host course, deliberately separate from original numeric course IDs.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct CustomTrack {
    pub id: &'static str,
    pub name: &'static str,
    pub peak_id: &'static str,
    pub event: EventKind,
    pub source: TrackSource,
    /// Name of the appended location in the derived BAM archive.
    pub world_location: &'static str,
    /// Native SSX 3 event whose race state supplies gameplay and UI flow.
    pub template_event: &'static str,
    /// World location associated with that native event.
    pub template_location: &'static str,
}

pub const PEAKS: &[CustomPeak] = &[CustomPeak {
    id: "bonus",
    name: "Bonus",
}];

pub const TRACKS: &[CustomTrack] = &[CustomTrack {
    id: "garibaldi",
    name: "Garibaldi",
    peak_id: "bonus",
    event: EventKind::Race,
    source: TrackSource::TrickyPs2 {
        archive: "DATA/MODELS/GARI.BIG",
    },
    world_location: "GARI",
    template_event: "ARA1",
    template_location: "ARA1",
}];

// Zero means that the game follows only the original event/section tables.
// The stored index is one-based so later custom courses need no new flag.
static ACTIVE: AtomicUsize = AtomicUsize::new(0);
static ACTIVE_WORLD_SECTION: AtomicU32 = AtomicU32::new(u32::MAX);
static TEMPLATE_WORLD_SECTION: AtomicU32 = AtomicU32::new(u32::MAX);
static LEASED_MAP_SLOT: AtomicU32 = AtomicU32::new(u32::MAX);
static BONUS_SELECTED: AtomicBool = AtomicBool::new(false);
static ASSETS_AVAILABLE: AtomicBool = AtomicBool::new(false);
static TRACK_INFO: AtomicU32 = AtomicU32::new(0);
static MENU_ACTION_FRAME: AtomicU32 = AtomicU32::new(u32::MAX);
// The template's native loading code consumes one fixed 40-byte residency
// row. Lease it while the custom event is active and restore it on return.
// Its sky and shared transport assets remain native; its terrain connectors
// are excluded so they cannot overlap Garibaldi or run Snow Jam scripts.
static RESIDENCY_ROW: Mutex<Option<[u8; 40]>> = Mutex::new(None);
const TEMPLATE_RESIDENCY: u32 = 0x0044_2488;

/// Build a separate metadata record so loading screens and results can use
/// the custom name without changing the retail TrackInfo array.
pub fn prepare_track_info(c: &mut Cpu, back: u32) -> crate::call::Flow {
    if active().is_none() || TRACK_INFO.load(Ordering::Acquire) != 0 {
        return Ok(());
    }
    use ssx3_ee_rt::cpu::{reg::*, sx};
    const TEMPLATE: u32 = 0x0043_d950;
    c.g[A0][0] = 100;
    c.g[A1][0] = sx(TEMPLATE + 4);
    c.g[A2][0] = 0x100;
    c.g[A3][0] = 0;
    crate::call::call_ptr(c, 0x0031_7d70, back)?;
    let pointer = c.g[V0][0] as u32;
    if pointer != 0 {
        for offset in 0..100 {
            let value = c.bus.read8(TEMPLATE + offset);
            c.bus.write8(pointer + offset, value);
        }
        // TrackInfo contains a display name, whereas UIText uses locale IDs.
        let name = b"Garibaldi\0";
        for offset in 0..48 {
            c.bus.write8(
                pointer + 4 + offset,
                name.get(offset as usize).copied().unwrap_or(0),
            );
        }
        TRACK_INFO.store(pointer, Ordering::Release);
    }
    Ok(())
}

pub fn track_info() -> Option<u32> {
    if active().is_none() {
        return None;
    }
    let pointer = TRACK_INFO.load(Ordering::Acquire);
    (pointer != 0).then_some(pointer)
}

pub fn set_assets_available(available: bool) {
    ASSETS_AVAILABLE.store(available, Ordering::Release);
}

pub fn assets_available() -> bool {
    ASSETS_AVAILABLE.load(Ordering::Acquire)
}

/// The custom menu category is separate from the guest's three-peak index.
pub fn select_bonus_peak() {
    BONUS_SELECTED.store(true, Ordering::Release);
}

pub fn bonus_peak_selected() -> bool {
    BONUS_SELECTED.load(Ordering::Acquire)
}

/// Newly enabled menus occur later in the screen's input traversal. Consume
/// the current press once so it cannot also accept Race and Garibaldi.
pub fn accept_menu_step(c: &mut Cpu) -> bool {
    let frame = crate::tick::vsync_count(c);
    MENU_ACTION_FRAME.swap(frame, Ordering::AcqRel) != frame
}

pub fn peak(id: &str) -> Option<&'static CustomPeak> {
    PEAKS.iter().find(|peak| peak.id == id)
}

pub fn track(id: &str) -> Option<&'static CustomTrack> {
    TRACKS.iter().find(|track| track.id == id)
}

pub fn tracks_on_peak(id: &str) -> impl Iterator<Item = &'static CustomTrack> + '_ {
    TRACKS.iter().filter(move |track| track.peak_id == id)
}

/// Select a host course before entering the native SSX 3 race flow.
pub fn activate(id: &str) -> Option<&'static CustomTrack> {
    let index = TRACKS.iter().position(|track| track.id == id)?;
    if ACTIVE.load(Ordering::Acquire) == index + 1 {
        return TRACKS.get(index);
    }
    ACTIVE_WORLD_SECTION.store(u32::MAX, Ordering::Release);
    TEMPLATE_WORLD_SECTION.store(u32::MAX, Ordering::Release);
    ACTIVE.store(index + 1, Ordering::Release);
    TRACKS.get(index)
}

/// Restore the original event-to-world mapping on return to Single Event.
pub fn deactivate(c: &mut Cpu) {
    let slot = LEASED_MAP_SLOT.swap(u32::MAX, Ordering::AcqRel);
    let template = TEMPLATE_WORLD_SECTION.load(Ordering::Acquire);
    let custom = ACTIVE_WORLD_SECTION.load(Ordering::Acquire);
    if slot < 49 && template != u32::MAX && custom != u32::MAX {
        let address = 0x0044_216c + slot * 16;
        if c.bus.read32(address) == custom {
            c.bus.write32(address, template);
        }
    }
    if let Some(original) = RESIDENCY_ROW.lock().unwrap().take() {
        for (offset, value) in original.into_iter().enumerate() {
            c.bus.write8(TEMPLATE_RESIDENCY + offset as u32, value);
        }
    }
    BONUS_SELECTED.store(false, Ordering::Release);
    ACTIVE.store(0, Ordering::Release);
    ACTIVE_WORLD_SECTION.store(u32::MAX, Ordering::Release);
    TEMPLATE_WORLD_SECTION.store(u32::MAX, Ordering::Release);
}

pub fn active() -> Option<&'static CustomTrack> {
    let one_based = ACTIVE.load(Ordering::Acquire);
    one_based.checked_sub(1).and_then(|index| TRACKS.get(index))
}

/// Resolve the appended BAM location and lease the native template's logical
/// section slot to it for the active custom race. The original slot value is
/// recreated by SectionMan_Init whenever the normal event screen is entered.
/// No extra entry is written to the game's fixed 50-slot logical table.
pub fn remap_section(c: &mut Cpu, section_man: u32) {
    let Some(track) = active() else { return };
    let game = c.bus.read32(section_man.wrapping_add(0x1b0));
    if game == 0 {
        return;
    }
    let world = c.bus.read32(game.wrapping_add(0x10));
    if world == 0 {
        return;
    }
    let cache = c.bus.read32(world);
    if cache == 0 {
        return;
    }
    let sdb = c.bus.read32(cache.wrapping_add(0x14));
    if sdb == 0 {
        eprintln!("custom track {}: world index has not loaded", track.id);
        return;
    }
    let count = c.bus.read32(sdb.wrapping_add(8));
    if count > 255 {
        eprintln!(
            "custom track {}: unsupported world section count {count}",
            track.id
        );
        return;
    }
    let find = |name: &str, c: &Cpu| -> Option<u32> {
        (0..count).find(|&index| {
            let name_at = sdb.wrapping_add(80 + index * 88);
            c.bus.read_cstr(name_at).eq_ignore_ascii_case(name)
        })
    };
    let (Some(template), Some(custom)) = (
        find(track.template_location, c),
        find(track.world_location, c),
    ) else {
        eprintln!(
            "custom track {}: BAM lacks {} or {}",
            track.id, track.template_location, track.world_location
        );
        return;
    };
    let map = 0x0044_216c_u32;
    let slots: Vec<_> = (0..49)
        .filter(|&slot| c.bus.read32(map + slot * 16) == template)
        .collect();
    if slots.len() != 1 {
        eprintln!(
            "custom track {}: expected one logical section for {}, found {}",
            track.id,
            track.template_location,
            slots.len()
        );
        return;
    }
    c.bus.write32(map + slots[0] * 16, custom);
    let mut residency = RESIDENCY_ROW.lock().unwrap();
    if residency.is_none() {
        let mut original = [0; 40];
        for (offset, value) in original.iter_mut().enumerate() {
            *value = c.bus.read8(TEMPLATE_RESIDENCY + offset as u32);
        }
        *residency = Some(original);
    }
    c.bus.write32(TEMPLATE_RESIDENCY + 4, 1);
    c.bus.write32(TEMPLATE_RESIDENCY + 0x10, slots[0]);
    LEASED_MAP_SLOT.store(slots[0], Ordering::Release);
    TEMPLATE_WORLD_SECTION.store(template, Ordering::Release);
    ACTIVE_WORLD_SECTION.store(custom, Ordering::Release);
}

/// Redirect the template event's world-section lookup only while its custom
/// section is active. Other events and all unmodified sessions use retail IDs.
pub fn event_world_section(original: u32) -> u32 {
    if active().is_none() {
        return original;
    }
    let custom = ACTIVE_WORLD_SECTION.load(Ordering::Acquire);
    if custom == u32::MAX {
        return original;
    }
    // The template's current world index is looked up from the SDB by
    // remap_section. The original event lookup identifies it by the same
    // location name in the retail table; the value is cached below.
    let template = TEMPLATE_WORLD_SECTION.load(Ordering::Acquire);
    if original == template {
        custom
    } else {
        original
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn every_custom_track_has_a_unique_id_and_registered_peak() {
        for (index, track) in TRACKS.iter().enumerate() {
            assert!(peak(track.peak_id).is_some());
            assert!(!TRACKS[index + 1..].iter().any(|later| later.id == track.id));
            assert_eq!(super::track(track.id), Some(track));
        }
        assert_eq!(
            tracks_on_peak("bonus")
                .map(|track| track.id)
                .collect::<Vec<_>>(),
            vec!["garibaldi"]
        );
    }
}
