//! Host-owned catalog for additional Single Event courses.
//!
//! IDs here never index the guest's 17-entry TrackInfo table or its career
//! save records. Menu and race integration can look up an entry by its stable
//! string ID, then resolve its own world and race data.

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
}];

pub fn peak(id: &str) -> Option<&'static CustomPeak> {
    PEAKS.iter().find(|peak| peak.id == id)
}

pub fn track(id: &str) -> Option<&'static CustomTrack> {
    TRACKS.iter().find(|track| track.id == id)
}

pub fn tracks_on_peak(id: &str) -> impl Iterator<Item = &'static CustomTrack> + '_ {
    TRACKS.iter().filter(move |track| track.peak_id == id)
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
        assert_eq!(tracks_on_peak("bonus").map(|track| track.id).collect::<Vec<_>>(),
                   vec!["garibaldi"]);
    }
}
