//! Host-only context for bounded observations of imported-course rendering.
//! No game memory, draw state, capture or timing is changed here.

use std::sync::Mutex;

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct Course {
    pub id: Option<&'static str>,
    pub run: u64,
}

static COURSE: Mutex<Course> = Mutex::new(Course { id: None, run: 0 });

pub fn set_course(id: Option<&'static str>) {
    let mut course = COURSE.lock().unwrap();
    if course.id != id {
        course.id = id;
        course.run = course.run.wrapping_add(1);
    }
}

pub fn restart() {
    let mut course = COURSE.lock().unwrap();
    course.run = course.run.wrapping_add(1);
}

pub fn course() -> Course {
    *COURSE.lock().unwrap()
}
