









mod alloc_count;
use engine_core::action::JointAction;
use engine_core::battle::Battle;
use engine_core::legal::{self, SideMask, SLOT_ACTIONS};
use engine_core::pending::Pending;
use engine_core::stats::Nature;
use engine_core::team::{self, MonSet, SetGender};
use engine_data::lookup;
use engine_obs::{ObsContext, SheetMon, TeamSheet, BROUGHT_SIZE, ROSTER_SIZE};
use numpy::{PyReadonlyArrayDyn, PyReadwriteArrayDyn};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use rayon::prelude::*;


#[derive(Clone, Copy)]
struct Team {
    sets: [MonSet; ROSTER_SIZE],
    sheet: TeamSheet,
    format: engine_core::rules::Format,
}

#[derive(Clone, Copy)]
struct Slot {
    battle: Battle,
    ctx: ObsContext,

    failed: bool,
}


#[pyclass(module = "vgc_engine")]
pub struct BattlePool {
    slots: Vec<Option<Slot>>,
    teams: Vec<Team>,

    errors: std::sync::Mutex<Vec<String>>,
}

fn err(msg: impl Into<String>) -> PyErr {
    PyValueError::new_err(msg.into())
}

fn slice_mut<'a, T: numpy::Element>(arr: &'a mut PyReadwriteArrayDyn<'_, T>, len: usize, name: &str) -> PyResult<&'a mut [T]> {
    let s = arr.as_slice_mut().map_err(|_| err(format!("{name} must be C-contiguous")))?;
    if s.len() != len {
        return Err(err(format!("{name} has {} elements, expected {len}", s.len())));
    }
    Ok(s)
}


fn parse_set(set: &Bound<'_, PyDict>, rules: &engine_core::rules::Rules) -> PyResult<MonSet> {
    let get_str = |key: &str| -> PyResult<String> {
        Ok(match set.get_item(key)? {
            Some(v) if !v.is_none() => v.extract::<String>()?,
            _ => String::new(),
        })
    };
    let species_name = get_str("species")?;
    let species = lookup::species(&species_name).ok_or_else(|| err(format!("unknown species {species_name:?}")))?;
    let ability_name = get_str("ability")?;
    let ability = if ability_name.is_empty() { 0 } else { lookup::ability(&ability_name).ok_or_else(|| err(format!("unknown ability {ability_name:?}")))? };
    let item_name = get_str("item")?;
    let item = if item_name.is_empty() { 0 } else { lookup::item(&item_name).ok_or_else(|| err(format!("unknown item {item_name:?}")))? };
    let mut moves = [0u16; 4];
    if let Some(list) = set.get_item("moves")? {
        let list = list.cast_into::<PyList>()?;
        if list.len() > 4 {
            return Err(err("a set has at most 4 moves"));
        }
        for (i, m) in list.iter().enumerate() {
            let name: String = m.extract()?;
            moves[i] = lookup::move_id(&name).ok_or_else(|| err(format!("unknown move {name:?}")))?;
        }
    }
    let mut ivs = [31u8; 6];
    if let Some(v) = set.get_item("ivs")? {
        let v = v.cast_into::<PyDict>()?;
        for (i, key) in ["hp", "atk", "def", "spa", "spd", "spe"].iter().enumerate() {
            if let Some(x) = v.get_item(*key)? {
                let iv: u32 = x.extract()?;
                if iv > 31 {
                    return Err(err(format!("IVs are 0-31, got {key}={iv}")));
                }
                ivs[i] = iv as u8;
            }
        }
    }

    if let Some(list) = set.get_item("moves")? {
        for m in list.cast_into::<PyList>()?.iter() {
            let name: String = m.extract()?;
            if let Some(Some(t)) = lookup::hidden_power_named_type(&name) {
                let from_ivs = team::hidden_power(ivs).0;
                if from_ivs != t {
                    return Err(err(format!("{name:?} with IVs {ivs:?}: those IVs give Hidden Power {from_ivs:?}")));
                }
            }
        }
    }
    let nature_name = get_str("nature")?;
    let nature_name = if nature_name.is_empty() { "hardy".to_string() } else { lookup::to_id(&nature_name) };
    let nature = Nature::from_id(&nature_name).ok_or_else(|| err(format!("unknown nature {nature_name:?}")))?;
    let mut stat_points = [0u8; 6];

    let max_invest = if rules.stat_formula == engine_core::rules::StatFormula::ChampionsPoints { 32 } else { 255 };
    if let Some(evs) = set.get_item("evs")? {
        let evs = evs.cast_into::<PyDict>()?;
        for (i, key) in ["hp", "atk", "def", "spa", "spd", "spe"].iter().enumerate() {
            if let Some(v) = evs.get_item(*key)? {
                let p: u32 = v.extract()?;
                if p > max_invest {
                    return Err(err(format!("evs are 0-{max_invest} in this format, got {key}={p}")));
                }
                stat_points[i] = p as u8;
            }
        }
    }
    let gender = match get_str("gender")?.as_str() {
        "M" => SetGender::Male,
        "F" => SetGender::Female,
        "N" => SetGender::Genderless,
        "" => SetGender::Unspecified,
        g => return Err(err(format!("unknown gender {g:?} (M, F, N or empty)"))),
    };

    let happiness = match set.get_item("happiness")? {
        Some(v) => v.extract::<u32>()?.min(255) as u8,
        None => 255,
    };


    let tera_type = match set.get_item("teraType")? {
        Some(v) if !v.is_none() && !v.extract::<String>()?.is_empty() => {
            let name = v.extract::<String>()?;
            Some(engine_data::type_chart::Type::from_name(&name).ok_or_else(|| err(format!("unknown teraType {name:?}")))?)
        }
        _ => required_tera_type(species),
    };

    let dynamax_level = match set.get_item("dynamaxLevel")? {
        Some(v) if !v.is_none() => v.extract::<u8>()?.min(10),
        _ => 10,
    };
    let gigantamax = match set.get_item("gigantamax")? {
        Some(v) if !v.is_none() => v.extract::<bool>()?,
        _ => false,
    };
    Ok(MonSet { species, ability, item, moves, nature, stat_points, ivs, gender, happiness, tera_type, dynamax_level, gigantamax })
}


fn required_tera_type(species: u16) -> Option<engine_data::type_chart::Type> {
    use engine_data::species_table::species_ids::*;
    use engine_data::type_chart::Type;
    match species {
        OGERPON | OGERPONTEALTERA => Some(Type::Grass),
        OGERPONWELLSPRING | OGERPONWELLSPRINGTERA => Some(Type::Water),
        OGERPONHEARTHFLAME | OGERPONHEARTHFLAMETERA => Some(Type::Fire),
        OGERPONCORNERSTONE | OGERPONCORNERSTONETERA => Some(Type::Rock),
        TERAPAGOS | TERAPAGOSTERASTAL | TERAPAGOSSTELLAR => Some(Type::Stellar),
        _ => None,
    }
}



fn moot_z(mask: &SideMask, k: usize, (index, g): (usize, bool)) -> (usize, bool) {
    let m = &mask.slots[k];
    (index, g && !(!m.mega && m.z_moves != 0 && !m.allows_gimmick(index)))
}

#[pymethods]
impl BattlePool {
    #[new]
    fn new(n: usize) -> Self {
        BattlePool { slots: vec![None; n], teams: Vec::new(), errors: std::sync::Mutex::new(Vec::new()) }
    }


    fn __len__(&self) -> usize {
        self.slots.len()
    }




    #[pyo3(signature = (sets, format=None))]
    fn register_team(&mut self, sets: &Bound<'_, PyList>, format: Option<&str>) -> PyResult<usize> {
        let format = match format {
            None => engine_core::rules::Format::ChampionsMC,
            Some(id) => engine_core::rules::Format::from_id(id).ok_or_else(|| err(format!("unknown format {id:?}")))?,
        };
        let rules = engine_core::rules::Rules::of(format);
        if sets.len() != ROSTER_SIZE {
            return Err(err(format!("a team has {ROSTER_SIZE} sets, got {}", sets.len())));
        }
        let mut parsed = [MonSet { species: 0, ability: 0, item: 0, moves: [0; 4], nature: Nature::neutral(), stat_points: [0; 6], ivs: [31; 6],
                                   gender: SetGender::Unspecified, happiness: 255, tera_type: None, dynamax_level: 10, gigantamax: false }; ROSTER_SIZE];
        let mut sheet = TeamSheet::default();
        for (i, s) in sets.iter().enumerate() {
            let set = parse_set(&s.cast_into::<PyDict>()?, rules)?;
            if let Some(what) = team::unsupported(&set) {
                return Err(err(format!("set {i}: {what}")));
            }
            let ability = if set.ability == 0 { rules.species_data(set.species).abilities[0] } else { set.ability };

            let tera_type = if rules.terastallization {
                set.tera_type.or(rules.species_data(set.species).types[0]).map_or(0, |t| t as u8 + 1)
            } else {
                0
            };
            sheet.mons[i] = SheetMon { species: set.species, item: set.item, ability, moves: set.moves, tera_type };
            parsed[i] = set;
        }
        self.teams.push(Team { sets: parsed, sheet, format });
        Ok(self.teams.len() - 1)
    }




    #[pyo3(signature = (team, out, as_opponent=false, open=false))]
    fn sheet_ids(&self, team: usize, mut out: PyReadwriteArrayDyn<'_, i32>, as_opponent: bool, open: bool) -> PyResult<()> {
        let t = self.teams.get(team).ok_or_else(|| err(format!("unknown team id {team}")))?;
        let rules = engine_core::rules::Rules::of(t.format);
        let known = !as_opponent || rules.open_team_sheets || open;
        let out = slice_mut(&mut out, ROSTER_SIZE * engine_obs::MON_IDS, "out")?;
        out.fill(0);
        for (r, m) in t.sheet.mons.iter().enumerate() {
            let row = &mut out[r * engine_obs::MON_IDS..(r + 1) * engine_obs::MON_IDS];
            row[engine_obs::mon_id::SPECIES] = m.species as i32;
            if known {
                row[engine_obs::mon_id::ITEM] = m.item as i32;
                row[engine_obs::mon_id::ABILITY] = m.ability as i32;
                for k in 0..4 {
                    row[engine_obs::mon_id::MOVES + k] = m.moves[k] as i32;
                }
            }
            let types = rules.species_data(m.species).types;
            for k in 0..2 {
                row[engine_obs::mon_id::TYPES + k] = types[k].map_or(0, |t| t as i32 + 1);
            }

            if known {
                row[engine_obs::mon_id::TERA_TYPE] = m.tera_type as i32;
            }
        }
        Ok(())
    }



    fn reset(&mut self, indices: Vec<usize>, teams: Vec<(usize, usize)>, bring: Vec<[[u8; BROUGHT_SIZE]; 2]>, seeds: Vec<u64>) -> PyResult<()> {
        if teams.len() != indices.len() || bring.len() != indices.len() || seeds.len() != indices.len() {
            return Err(err("reset: indices, teams, bring and seeds must have the same length"));
        }
        for k in 0..indices.len() {
            let i = indices[k];
            if i >= self.slots.len() {
                return Err(err(format!("pool index {i} out of range")));
            }
            let pair = [teams[k].0, teams[k].1];
            let format = self.teams.get(pair[0]).ok_or_else(|| err(format!("unknown team id {}", pair[0])))?.format;
            if self.teams.get(pair[1]).map(|t| t.format) != Some(format) {
                return Err(err(format!("teams {} and {} are not of one format", pair[0], pair[1])));
            }
            let rules = engine_core::rules::Rules::of(format);
            let mut sides = Vec::with_capacity(2);
            let mut ctx = ObsContext::default();
            for side in 0..2 {
                let t = self.teams.get(pair[side]).ok_or_else(|| err(format!("unknown team id {}", pair[side])))?;
                let b = bring[k][side];
                let mut seen = [false; ROSTER_SIZE];
                for &r in &b {
                    if r as usize >= ROSTER_SIZE || seen[r as usize] {
                        return Err(err(format!("bring must be 4 distinct sheet indices 0-5, got {b:?}")));
                    }
                    seen[r as usize] = true;
                }
                sides.push(alloc_count::counted(3, || team::build_side(b.map(|r| team::build_mon_in(rules, &t.sets[r as usize])))));
                ctx.sheets[side] = t.sheet;
                ctx.brought[side] = b;
            }
            self.slots[i] = Some(Slot { battle: alloc_count::counted(3, || team::new_battle_in(format, [sides[0], sides[1]], seeds[k])), ctx, failed: false });
        }
        Ok(())
    }



    fn observe(
        &self,
        py: Python<'_>,
        side: u8,
        mut field: PyReadwriteArrayDyn<'_, f32>,
        mut mon_ids: PyReadwriteArrayDyn<'_, i32>,
        mut mon_features: PyReadwriteArrayDyn<'_, f32>,
        mut history: PyReadwriteArrayDyn<'_, i32>,
    ) -> PyResult<()> {
        if side > 1 {
            return Err(err("side is 0 or 1"));
        }
        let n = self.slots.len();
        let [fs, is, ms, hs] = engine_obs::BUFFER_SIZES;
        let field = slice_mut(&mut field, n * fs, "field")?;
        let mon_ids = slice_mut(&mut mon_ids, n * is, "mon_ids")?;
        let mon_features = slice_mut(&mut mon_features, n * ms, "mon_features")?;
        let history = slice_mut(&mut history, n * hs, "history")?;
        let slots = &self.slots;
        py.detach(|| {
            field
                .par_chunks_mut(fs)
                .zip(mon_ids.par_chunks_mut(is))
                .zip(mon_features.par_chunks_mut(ms))
                .zip(history.par_chunks_mut(hs))
                .zip(slots.par_iter())
                .for_each(|((((f, ids), feats), hist), slot)| match slot {
                    Some(s) => alloc_count::counted(1, || engine_obs::encode(&s.battle, &s.ctx, side, engine_obs::ObsBuffers { field: f, mon_ids: ids, mon_features: feats, history: hist })),
                    None => {
                        f.fill(0.0);
                        ids.fill(0);
                        feats.fill(0.0);
                        hist.fill(0);
                    }
                });
        });
        Ok(())
    }









    #[pyo3(signature = (actions, mega, to_move, min_switches, gimmick=None, forced=None, kind=None))]
    #[allow(clippy::too_many_arguments)]
    fn masks(
        &self,
        py: Python<'_>,
        mut actions: PyReadwriteArrayDyn<'_, u32>,
        mut mega: PyReadwriteArrayDyn<'_, bool>,
        mut to_move: PyReadwriteArrayDyn<'_, bool>,
        mut min_switches: PyReadwriteArrayDyn<'_, u8>,
        gimmick: Option<PyReadwriteArrayDyn<'_, u32>>,
        forced: Option<PyReadwriteArrayDyn<'_, u32>>,
        kind: Option<PyReadwriteArrayDyn<'_, u8>>,
    ) -> PyResult<()> {
        let n = self.slots.len();
        let actions = slice_mut(&mut actions, n * 4, "actions")?;
        let mega = slice_mut(&mut mega, n * 4, "mega")?;
        let to_move = slice_mut(&mut to_move, n * 2, "to_move")?;
        let min_switches = slice_mut(&mut min_switches, n * 2, "min_switches")?;
        let (mut gimmick, mut forced, mut kind) = match (gimmick, forced, kind) {
            (Some(g), Some(f), Some(k)) => (Some(g), Some(f), Some(k)),
            (None, None, None) => (None, None, None),
            _ => return Err(err("masks: pass gimmick, forced and kind together, or none of them")),
        };

        let (mut g_tmp, mut f_tmp, mut k_tmp) = (Vec::new(), Vec::new(), Vec::new());
        let gimmick = match gimmick.as_mut() {
            Some(g) => slice_mut(g, n * 4, "gimmick")?,
            None => {
                g_tmp.resize(n * 4, 0u32);
                &mut g_tmp[..]
            }
        };
        let forced = match forced.as_mut() {
            Some(f) => slice_mut(f, n * 4, "forced")?,
            None => {
                f_tmp.resize(n * 4, 0u32);
                &mut f_tmp[..]
            }
        };
        let kind = match kind.as_mut() {
            Some(k) => slice_mut(k, n * 4, "kind")?,
            None => {
                k_tmp.resize(n * 4, 0u8);
                &mut k_tmp[..]
            }
        };
        let slots = &self.slots;
        py.detach(|| {
            actions
                .par_chunks_mut(4)
                .zip(mega.par_chunks_mut(4))
                .zip(to_move.par_chunks_mut(2))
                .zip(min_switches.par_chunks_mut(2))
                .zip(gimmick.par_chunks_mut(4))
                .zip(forced.par_chunks_mut(4))
                .zip(kind.par_chunks_mut(4))
                .zip(slots.par_iter())
                .for_each(|(((((((a, m), t), ms), g), f), kd), slot)| {
                    for side in 0..2 {
                        let mask = slot.map_or(SideMask::default(), |s| alloc_count::counted(2, || legal::side_mask(&s.battle, side as u8)));
                        t[side] = mask.to_move;
                        ms[side] = mask.min_switches;
                        for k in 0..2 {
                            let sm = &mask.slots[k];
                            a[side * 2 + k] = sm.plain_actions();
                            m[side * 2 + k] = sm.mega || sm.z_moves != 0;
                            (g[side * 2 + k], f[side * 2 + k], kd[side * 2 + k]) = alloc_count::counted(2, || sm.gimmick_masks());
                        }
                    }
                });
        });
        Ok(())
    }



    #[pyo3(signature = (actions, only=None))]
    fn step(&mut self, py: Python<'_>, actions: PyReadonlyArrayDyn<'_, i32>, only: Option<Vec<usize>>) -> PyResult<()> {
        let n = self.slots.len();
        let selected: Option<Vec<bool>> = only.map(|v| {
            let mut m = vec![false; n];
            for i in v {
                if i < n {
                    m[i] = true;
                }
            }
            m
        });
        let skip = |i: usize| selected.as_ref().map_or(false, |m| !m[i]);
        let a = actions.as_slice().map_err(|_| err("actions must be C-contiguous"))?;
        if a.len() != n * 8 {
            return Err(err(format!("actions has {} elements, expected {}", a.len(), n * 8)));
        }
        let choice = |i: usize, side: usize, slot: usize| -> (usize, bool) {
            let base = i * 8 + side * 4 + slot * 2;
            (a[base].clamp(0, SLOT_ACTIONS as i32 - 1) as usize, a[base + 1] != 0)
        };

        for (i, slot) in self.slots.iter().enumerate() {
            let Some(s) = slot else { continue };
            if s.failed || matches!(s.battle.pending, Pending::Over { .. }) || skip(i) {
                continue;
            }
            for side in 0..2 {
                let mask = legal::side_mask(&s.battle, side as u8);
                if !mask.to_move {
                    continue;
                }
                let joint = [moot_z(&mask, 0, choice(i, side, 0)), moot_z(&mask, 1, choice(i, side, 1))];
                let raw = (a[i * 8 + side * 4], a[i * 8 + side * 4 + 2]);
                if raw.0 < 0 || raw.0 >= SLOT_ACTIONS as i32 || raw.1 < 0 || raw.1 >= SLOT_ACTIONS as i32 || !legal::joint_is_legal(&mask, joint) {
                    return Err(err(format!("battle {i} side {side}: illegal choice {joint:?} (mask {mask:?})")));
                }
            }
        }
        let slots = &mut self.slots;
        let errors = &self.errors;
        py.detach(|| {
            slots.par_iter_mut().enumerate().for_each(|(i, slot)| {
                let Some(s) = slot else { return };
                if s.failed || matches!(s.battle.pending, Pending::Over { .. }) || skip(i) {
                    return;
                }
                let mut joint: [JointAction; 2] = [[engine_core::action::Action::Pass; 2]; 2];
                for side in 0..2 {
                    let mask = alloc_count::counted(2, || legal::side_mask(&s.battle, side as u8));
                    if !mask.to_move {
                        continue;
                    }
                    for k in 0..2 {
                        let (index, mega) = moot_z(&mask, k, choice(i, side, k));
                        joint[side][k] = alloc_count::counted(0, || legal::decode(&s.battle, side as u8, k as u8, index, mega));
                    }
                }
                let mut next = s.battle;
                match std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| alloc_count::counted(0, || engine_core::turn::step(&mut next, joint)))) {
                    Ok(()) => s.battle = next,
                    Err(e) => {
                        let msg = e.downcast_ref::<String>().cloned().or_else(|| e.downcast_ref::<&str>().map(|m| m.to_string())).unwrap_or_default();
                        errors.lock().unwrap().push(format!("battle {i} turn {}: {msg}", s.battle.turn));
                        s.failed = true;
                    }
                }
            });
        });
        Ok(())
    }







    fn step_scripted<'py>(&mut self, py: Python<'py>, index: usize, actions: [[[i32; 2]; 2]; 2],
                          overrides: Vec<(u8, u8, u16, u8, u8, u32)>) -> PyResult<Bound<'py, PyDict>> {
        use engine_core::rng::{script, Site};
        let slot = self.slots.get_mut(index).and_then(|s| s.as_mut()).ok_or_else(|| err(format!("no battle in slot {index}")))?;
        if slot.failed || matches!(slot.battle.pending, Pending::Over { .. }) {
            return Err(err("step_scripted: the battle is over or failed"));
        }
        let site = |v: u8| -> PyResult<Site> {
            Ok(match v { 1 => Site::Accuracy, 2 => Site::Crit, 3 => Site::DamageRoll, 4 => Site::Secondary, 5 => Site::Flinch,
                         6 => Site::Confusion, 7 => Site::FullParalysis, 8 => Site::ConfusionSelfHit, 9 => Site::SleepTurns,
                         10 => Site::Thaw, 11 => Site::QuickClaw, _ => return Err(err(format!("unknown draw site {v}"))) })
        };
        let ovr = overrides.iter().map(|&(s, actor, move_id, target, k, value)| Ok(script::Override { site: site(s)?, actor, move_id, target, k, value }))
            .collect::<PyResult<Vec<_>>>()?;
        let mut joint: [JointAction; 2] = [[engine_core::action::Action::Pass; 2]; 2];
        for side in 0..2 {
            let mask = legal::side_mask(&slot.battle, side as u8);
            if !mask.to_move {
                continue;
            }
            let raw = actions[side];
            if raw.iter().any(|a| a[0] < 0 || a[0] >= SLOT_ACTIONS as i32) {
                return Err(err(format!("side {side}: action out of range {raw:?}")));
            }
            let pick = [moot_z(&mask, 0, (raw[0][0] as usize, raw[0][1] != 0)), moot_z(&mask, 1, (raw[1][0] as usize, raw[1][1] != 0))];
            if !legal::joint_is_legal(&mask, pick) {
                return Err(err(format!("side {side}: illegal choice {pick:?} (mask {mask:?})")));
            }
            for k in 0..2 {
                joint[side][k] = legal::decode(&slot.battle, side as u8, k as u8, pick[k].0, pick[k].1);
            }
        }
        let mut next = slot.battle;
        script::begin(&ovr);
        let run = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| engine_core::turn::step(&mut next, joint)));
        let (draws, unused) = script::end();
        if let Err(e) = run {
            let msg = e.downcast_ref::<String>().cloned().or_else(|| e.downcast_ref::<&str>().map(|m| m.to_string())).unwrap_or_default();
            return Err(err(format!("step_scripted: the engine panicked: {msg}")));
        }
        slot.battle = next;
        let mv = |id: u16| if id == 0 || id as usize > engine_data::moves_table::MOVE_COUNT { "" } else { engine_data::moves_table::name(id) };
        let out = PyDict::new(py);
        let list = PyList::empty(py);
        for d in draws {
            list.append((d.site as u8, d.actor, d.move_id, mv(d.move_id), d.target, d.k, d.bound, d.numerator, d.rolled, d.result, d.forced))?;
        }
        out.set_item("draws", list)?;
        out.set_item("unused", unused.iter().map(|o| (o.site as u8, o.actor, o.move_id, o.target, o.k, o.value)).collect::<Vec<_>>())?;
        Ok(out)
    }


    fn errors(&self) -> Vec<String> {
        std::mem::take(&mut *self.errors.lock().unwrap())
    }






    #[pyo3(signature = (side, seed, out, only=None))]
    fn greedy_actions(
        &self,
        py: Python<'_>,
        side: u8,
        seed: u64,
        mut out: PyReadwriteArrayDyn<'_, i32>,
        only: Option<PyReadonlyArrayDyn<'_, i64>>,
    ) -> PyResult<()> {
        if side > 1 {
            return Err(err("side is 0 or 1"));
        }
        let n = self.slots.len();
        let pick = match &only {
            None => None,
            Some(a) => {
                let mut m = vec![false; n];
                for &i in a.as_slice().map_err(|_| err("only must be C-contiguous"))? {
                    if i < 0 || i as usize >= n {
                        return Err(err("only: battle index out of range"));
                    }
                    m[i as usize] = true;
                }
                Some(m)
            }
        };
        let out = slice_mut(&mut out, n * 4, "out")?;
        let slots = &self.slots;
        py.detach(|| {
            out.par_chunks_mut(4).zip(slots.par_iter()).enumerate().for_each(|(i, (o, slot))| {
                let mut pairs = [(legal::PASS_ACTION, false); 2];
                let wanted = pick.as_ref().is_none_or(|m| m[i]);
                if let (true, Some(s)) = (wanted, slot) {
                    if !s.failed && !matches!(s.battle.pending, Pending::Over { .. }) {
                        let joint = engine_core::bots::greedy_damage(&s.battle, side, seed ^ (i as u64).wrapping_mul(0x9E37_79B9));
                        for k in 0..2 {
                            pairs[k] = legal::encode(&s.battle, side, k as u8, joint[k]);
                        }
                    }
                }
                for k in 0..2 {
                    o[k * 2] = pairs[k].0 as i32;
                    o[k * 2 + 1] = pairs[k].1 as i32;
                }
            });
        });
        Ok(())
    }



    fn status(&self, mut out: PyReadwriteArrayDyn<'_, i8>) -> PyResult<()> {
        let n = self.slots.len();
        let out = slice_mut(&mut out, n, "out")?;
        for (o, slot) in out.iter_mut().zip(&self.slots) {
            *o = match slot {
                None => -2,
                Some(s) if s.failed => -3,
                Some(s) => match s.battle.pending {
                    Pending::Over { winner: Some(w) } => w as i8,
                    Pending::Over { winner: None } => 2,
                    _ => -1,
                },
            };
        }
        Ok(())
    }


    fn turns(&self) -> Vec<u16> {
        self.slots.iter().map(|s| s.map_or(0, |s| s.battle.turn)).collect()
    }



    fn copy_from(&mut self, source: PyRef<'_, BattlePool>, src: Vec<usize>, dst: Vec<usize>, seeds: Vec<u64>) -> PyResult<()> {
        if src.len() != dst.len() || seeds.len() != dst.len() {
            return Err(err("copy_from: src, dst and seeds must have the same length"));
        }
        let mut copies = Vec::with_capacity(src.len());
        for (&i, &seed) in src.iter().zip(&seeds) {
            let mut s = source.slots.get(i).copied().ok_or_else(|| err(format!("source index {i} out of range")))?;
            if let Some(s) = s.as_mut() {
                s.battle.rng = engine_core::rng::Rng::new(seed);
            }
            copies.push(s);
        }
        for (&j, s) in dst.iter().zip(copies) {
            *self.slots.get_mut(j).ok_or_else(|| err(format!("pool index {j} out of range")))? = s;
        }
        Ok(())
    }



    fn hidden_bench(&self, indices: Vec<usize>, side: u8) -> PyResult<Vec<Vec<u8>>> {
        use engine_core::mon::mon_flags;
        let mut out = Vec::with_capacity(indices.len());
        for &i in &indices {
            let Some(slot) = self.slots.get(i).ok_or_else(|| err(format!("pool index {i} out of range")))?.as_ref() else {
                out.push(Vec::new());
                continue;
            };
            let s = &slot.battle.sides[side as usize & 1];
            if s.mons.iter().any(|m| m.illusion.is_some() || m.ability == engine_data::abilities_table::ability_ids::ILLUSION) {
                out.push(Vec::new());
                continue;
            }
            out.push(
                (0..s.mons.len() as u8)
                    .filter(|&k| {
                        let m = &s.mons[k as usize];
                        !s.active[..2].contains(&k) && !m.is_fainted() && !m.flags.has(mon_flags::REVEALED)
                    })
                    .collect(),
            );
        }
        Ok(out)
    }





    fn mask_hidden(&mut self, source: PyRef<'_, BattlePool>, indices: Vec<usize>, side: u8, teams: Vec<usize>, bench: Vec<Vec<(u8, u8)>>, hp_round: bool) -> PyResult<()> {
        use engine_core::mon::mon_flags;
        if indices.len() != teams.len() || indices.len() != bench.len() || side > 1 {
            return Err(err("mask_hidden: indices, teams and bench must have the same length, side 0 or 1"));
        }
        for ((&i, &tid), swaps) in indices.iter().zip(&teams).zip(&bench) {
            let team = source.teams.get(tid).ok_or_else(|| err(format!("unknown team id {tid}")))?;
            let Some(slot) = self.slots.get_mut(i).ok_or_else(|| err(format!("pool index {i} out of range")))?.as_mut() else { continue };
            for &(k, r) in swaps {
                let s = &mut slot.battle.sides[side as usize];
                let m = s.mons.get(k as usize).ok_or_else(|| err(format!("battle index {k}")))?;
                if s.active[..2].contains(&k) || m.is_fainted() || m.flags.has(mon_flags::REVEALED) {
                    return Err(err(format!("mask_hidden: battle mon {k} isn't hidden")));
                }
                let set = team.sets.get(r as usize).ok_or_else(|| err(format!("sheet index {r}")))?;
                s.mons[k as usize] = team::build_mon_in(engine_core::rules::Rules::of(team.format), set);
                slot.ctx.brought[side as usize][k as usize] = r;
            }
            if hp_round {
                for m in slot.battle.sides[side as usize].mons.iter_mut() {
                    if m.hp == 0 || m.hp >= m.max_hp {
                        continue;
                    }
                    let max = m.max_hp as u32;
                    let pct = ((m.hp as u32 * 100 + max - 1) / max).min(99);
                    m.hp = (((2 * pct - 1) * max + 100) / 200).clamp(1, max - 1) as u16;
                }
            }
        }
        Ok(())
    }




    fn set_spreads(&mut self, indices: Vec<usize>, side: u8, spreads: Vec<Vec<(String, [u8; 6])>>) -> PyResult<()> {
        if indices.len() != spreads.len() || side > 1 {
            return Err(err("set_spreads: indices and spreads must have the same length, side 0 or 1"));
        }
        for (&i, mons) in indices.iter().zip(&spreads) {
            let Some(slot) = self.slots.get_mut(i).ok_or_else(|| err(format!("pool index {i} out of range")))?.as_mut() else { continue };
            let rules = slot.battle.rules();
            for (mon, (nature, points)) in slot.battle.sides[side as usize].mons.iter_mut().zip(mons) {
                let nature_id = if nature.is_empty() { "hardy".to_string() } else { lookup::to_id(nature) };
                mon.nature = Nature::from_id(&nature_id).ok_or_else(|| err(format!("unknown nature {nature:?}")))?;
                mon.stat_points = *points;
                let (hp, old_max) = (mon.hp, mon.max_hp.max(1));
                mon.recalc_stats(rules, rules.species_data(mon.species).base_stats);
                if hp > 0 {
                    mon.hp = ((hp as u32 * mon.max_hp as u32 + old_max as u32 / 2) / old_max as u32).clamp(1, mon.max_hp as u32) as u16;
                }
            }
        }
        Ok(())
    }



    fn set_open_sheets(&mut self, indices: Vec<usize>, open: bool) -> PyResult<()> {
        for &i in &indices {
            if let Some(slot) = self.slots.get_mut(i).ok_or_else(|| err(format!("pool index {i} out of range")))?.as_mut() {
                slot.ctx.open_sheets = open;
            }
        }
        Ok(())
    }









    fn shown_sets(&self, index: usize, side: u8) -> PyResult<Vec<(String, Vec<String>, String, bool, Option<bool>, String)>> {
        use engine_core::mon::mon_flags;
        use engine_data::{abilities_table, items_table, moves_table, species_table};
        let slot = self.slots.get(index).and_then(|s| s.as_ref()).ok_or_else(|| err(format!("no battle in slot {index}")))?;
        if side > 1 {
            return Err(err("shown_sets: side 0 or 1"));
        }
        let rules = slot.battle.rules();
        let (sheet, brought) = (&slot.ctx.sheets[side as usize], &slot.ctx.brought[side as usize]);
        let s = &slot.battle.sides[side as usize];
        let open = rules.open_team_sheets || slot.ctx.open_sheets;
        let mut out = Vec::with_capacity(ROSTER_SIZE);
        for (r, sm) in sheet.mons.iter().enumerate() {
            if sm.species == 0 {
                continue;
            }
            let holds = rules.preview_shows_items.then_some(sm.item != 0);
            let species = species_table::get(sm.species).name.to_string();
            if open {
                let ability = if sm.ability == 0 { rules.species_data(sm.species).abilities[0] } else { sm.ability };
                let moves = sm.moves.iter().filter(|&&m| m != 0).map(|&m| moves_table::name(m).to_string()).collect();
                let item = if sm.item == 0 { String::new() } else { items_table::name(sm.item).to_string() };
                out.push((species, moves, item, false, Some(sm.item != 0), abilities_table::name(ability).to_string()));
                continue;
            }
            let live = brought.iter().position(|&b| b as usize == r).map(|k| &s.mons[k]).filter(|m| m.flags.has(mon_flags::REVEALED));
            let Some(m) = live else {
                out.push((species, Vec::new(), String::new(), false, holds, String::new()));
                continue;
            };
            let own = if m.flags.has(mon_flags::TRANSFORMED) { m.base_moves } else { m.moves };
            let moves = (0..4)
                .filter(|&k| m.moves_revealed & (1 << k) != 0 && own[k] != 0)
                .map(|k| moves_table::name(own[k]).to_string())
                .collect();
            let gone = sm.item != 0 && m.item == 0;
            let shown = if item_shows(rules, m) { m.item } else if gone { m.last_item } else { 0 };
            out.push((species, moves, if shown == 0 { String::new() } else { items_table::name(shown).to_string() }, gone, holds, String::new()));
        }
        Ok(out)
    }










    fn set_sets(&mut self, indices: Vec<usize>, side: u8, teams: Vec<usize>) -> PyResult<()> {
        use engine_core::mon::{mon_flags, volatile_flags};
        const NO_ABILITY: u16 = engine_core::ids::NONE_ID;
        if indices.len() != teams.len() || side > 1 {
            return Err(err("set_sets: indices and teams must have the same length, side 0 or 1"));
        }
        const KEEP_ABILITY: u64 = mon_flags::NGAS_SUPPRESSED
            | mon_flags::NGAS_LIVE
            | mon_flags::NGAS_ENDING
            | mon_flags::UNNERVED
            | mon_flags::TRACE_SEEK
            | mon_flags::SWORD_BOOST
            | mon_flags::SHIELD_BOOST
            | mon_flags::TRANSFORMED;
        for (&i, &tid) in indices.iter().zip(&teams) {
            let team = *self.teams.get(tid).ok_or_else(|| err(format!("unknown team id {tid}")))?;
            let Some(slot) = self.slots.get_mut(i).ok_or_else(|| err(format!("pool index {i} out of range")))?.as_mut() else { continue };
            let rules = slot.battle.rules();
            let open = rules.open_team_sheets || slot.ctx.open_sheets;
            let (sheet, brought) = (slot.ctx.sheets[side as usize], slot.ctx.brought[side as usize]);
            if (0..ROSTER_SIZE).any(|r| sheet.mons[r].species != team.sheet.mons[r].species) {
                return Err(err(format!("set_sets: team {tid}'s species differ from battle {i}'s sheet")));
            }
            for (k, m) in slot.battle.sides[side as usize].mons.iter_mut().enumerate() {
                let r = brought[k] as usize;
                let (g, sm) = (&team.sets[r], &sheet.mons[r]);
                let transformed = m.flags.has(mon_flags::TRANSFORMED);

                let revealed = if open { 0b1111 } else { m.moves_revealed };
                let (moves, pp) = if transformed { (&mut m.base_moves, &mut m.base_pp) } else { (&mut m.moves, &mut m.pp) };
                let kept: Vec<u16> = (0..4).filter(|&s| revealed & (1 << s) != 0).map(|s| moves[s]).collect();
                let hp_shown = kept.contains(&engine_data::moves_table::move_ids::HIDDENPOWER);
                let mut fill = g.moves.iter().copied().filter(|&x| x != 0 && !kept.contains(&x));
                for s in 0..4 {
                    if revealed & (1 << s) == 0 {
                        let x = fill.next().unwrap_or(0);
                        moves[s] = x;
                        pp[s] = if x == 0 { 0 } else { rules.max_pp(x) };
                    }
                }

                if !open && m.item == sm.item && !item_shows(rules, m) {
                    m.item = g.item;
                }

                let gastro = m.volatiles.has(volatile_flags::GASTRO_ACID);
                let real = if gastro { m.suppressed_ability } else { m.ability };
                let sheet_ability = if sm.ability == 0 { rules.species_data(sm.species).abilities[0] } else { sm.ability };
                let changed = real != sheet_ability || (m.base_ability != NO_ABILITY && m.base_ability != sheet_ability);
                if !open && !changed && !m.mega.active && m.illusion.is_none() && m.flags.0 & KEEP_ABILITY == 0 {
                    let new = if g.ability == 0 { rules.species_data(g.species).abilities[0] } else { g.ability };
                    if gastro {
                        m.suppressed_ability = new;
                    } else {
                        m.ability = new;
                    }
                    if m.base_ability != NO_ABILITY {
                        m.base_ability = new;
                    }
                }

                if !transformed && !m.flags.has(mon_flags::POWER_TRICK) && !m.flags.has(mon_flags::STATS_SPLIT) {
                    m.nature = g.nature;
                    m.stat_points = g.stat_points;
                    if !hp_shown {
                        m.ivs = g.ivs;
                    }
                    let (hp, old_max, regen) = (m.hp, m.max_hp.max(1), m.regen_hidden);
                    m.recalc_stats(rules, rules.species_data(m.species).base_stats);
                    keep_shown_hp(rules, m, hp, old_max, regen);
                }
                if !open && !m.flags.has(mon_flags::DYNAMAXED) {
                    m.flags.0 = (m.flags.0 & !mon_flags::GIGANTAMAX) | if g.gigantamax { mon_flags::GIGANTAMAX } else { 0 };
                }
            }
            if !open {
                slot.ctx.sheets[side as usize] = team.sheet;
            }
        }
        Ok(())
    }











    fn load_state(&mut self, index: usize, snapshot: &Bound<'_, PyDict>, seed: u64) -> PyResult<()> {
        if index >= self.slots.len() {
            return Err(err(format!("pool index {index} out of range")));
        }
        let pair: [usize; 2] = req(snapshot, "teams")?;
        let bring: [[u8; BROUGHT_SIZE]; 2] = req(snapshot, "bring")?;

        let format = self.teams.get(pair[0]).ok_or_else(|| err(format!("unknown team id {}", pair[0])))?.format;
        if self.teams.get(pair[1]).map(|t| t.format) != Some(format) {
            return Err(err(format!("teams {} and {} are not of one format", pair[0], pair[1])));
        }
        let format_rules = engine_core::rules::Rules::of(format);
        let mut sides = Vec::with_capacity(2);
        let mut ctx = ObsContext::default();
        for side in 0..2 {
            let t = self.teams.get(pair[side]).ok_or_else(|| err(format!("unknown team id {}", pair[side])))?;
            let b = bring[side];
            if b.iter().any(|&r| r as usize >= ROSTER_SIZE) || (0..4).any(|i| (i + 1..4).any(|j| b[i] == b[j])) {
                return Err(err(format!("bring must be 4 distinct sheet indices 0-5, got {b:?}")));
            }
            sides.push(team::build_side(b.map(|r| team::build_mon_in(format_rules, &t.sets[r as usize]))));
            ctx.sheets[side] = t.sheet;
            ctx.brought[side] = b;
        }
        ctx.open_sheets = opt::<bool>(snapshot, "open_sheets")?.unwrap_or(false);
        let mut battle = Battle {
            sides: [sides[0], sides[1]],
            field: engine_core::field::Field::default(),
            turn: opt::<u16>(snapshot, "turn")?.unwrap_or(1),
            rng: engine_core::rng::Rng::new(seed),
            pending: Pending::Turn,
            history: engine_core::event::EventRing::default(),
            resume: None,
            end_turn_pending: false,
            started: true,
            opportunist: [[0; 7]; 4],
            opportunist_bank: 0,
            format,
            speed_order: [0, 1, 2, 3],
            ability_seq: 0,
            dance_move: 0,
            active_target: 0,
        };
        if let Some(f) = opt::<Bound<'_, PyDict>>(snapshot, "field")? {
            use engine_core::field::{Terrain, Weather};
            let fl = &mut battle.field;
            if let Some(w) = opt::<u8>(&f, "weather")? {
                fl.weather = match w { 0 => Weather::None, 1 => Weather::Sun, 2 => Weather::Rain, 3 => Weather::Sand, 4 => Weather::Snow, 5 => Weather::Hail, 6 => Weather::DesolateLand, 7 => Weather::PrimordialSea, 8 => Weather::DeltaStream, _ => return Err(err(format!("weather {w}"))) };
            }
            if let Some(t) = opt::<u8>(&f, "terrain")? {
                fl.terrain = match t { 0 => Terrain::None, 1 => Terrain::Electric, 2 => Terrain::Grassy, 3 => Terrain::Misty, 4 => Terrain::Psychic, _ => return Err(err(format!("terrain {t}"))) };
            }
            set_opt(&f, "weather_turns", &mut fl.weather_turns)?;

            set_opt(&f, "weather_source", &mut fl.weather_source)?;
            set_opt(&f, "terrain_turns", &mut fl.terrain_turns)?;
            set_opt(&f, "trick_room", &mut fl.trick_room_turns)?;
            set_opt(&f, "gravity", &mut fl.gravity_turns)?;

            set_opt(&f, "hazard_seq", &mut fl.hazard_seq)?;

            set_opt(&f, "last_move", &mut fl.last_move)?;
            set_opt(&f, "last_move_z", &mut fl.last_move_z)?;
        }
        let side_dicts: Vec<Bound<'_, PyDict>> = req(snapshot, "sides")?;
        if side_dicts.len() != 2 {
            return Err(err("load_state: `sides` needs two entries"));
        }
        for (side, sd) in side_dicts.iter().enumerate() {
            let rules = battle.rules();
            let s = &mut battle.sides[side];
            if let Some(spreads) = opt::<Vec<(String, [u8; 6])>>(sd, "spreads")? {
                for (mon, (nature, points)) in s.mons.iter_mut().zip(spreads) {
                    let nature_id = if nature.is_empty() { "hardy".to_string() } else { lookup::to_id(&nature) };
                    mon.nature = Nature::from_id(&nature_id).ok_or_else(|| err(format!("unknown nature {nature:?}")))?;
                    mon.stat_points = points;
                    mon.recalc_stats(rules, rules.species_data(mon.species).base_stats);
                    mon.hp = mon.max_hp;
                }
            }
            if let Some(active) = opt::<[u8; 2]>(sd, "active")? {
                s.active[..2].copy_from_slice(&active);
            }
            set_opt(sd, "order", &mut s.order)?;
            set_opt(sd, "mega_used", &mut s.mega_used)?;

            set_opt(sd, "z_used", &mut s.z_used)?;
            set_opt(sd, "ultra_used", &mut s.ultra_used)?;

            set_opt(sd, "tera_used", &mut s.tera_used)?;

            set_opt(sd, "dynamax_used", &mut s.dynamax_used)?;
            set_opt(sd, "revivals", &mut s.revivals)?;
            if let Some(c) = opt::<Bound<'_, PyDict>>(sd, "conds")? {
                let sc = &mut s.side_conditions;
                set_opt(&c, "reflect", &mut sc.reflect_turns)?;
                set_opt(&c, "light_screen", &mut sc.light_screen_turns)?;
                set_opt(&c, "aurora_veil", &mut sc.aurora_veil_turns)?;
                set_opt(&c, "tailwind", &mut sc.tailwind_turns)?;
                set_opt(&c, "safeguard", &mut sc.safeguard_turns)?;
                set_opt(&c, "stealth_rock", &mut sc.stealth_rock)?;
                set_opt(&c, "spikes", &mut sc.spikes)?;
                set_opt(&c, "toxic_spikes", &mut sc.toxic_spikes)?;
                set_opt(&c, "sticky_web", &mut sc.sticky_web)?;

                set_opt(&c, "steelsurge", &mut sc.steelsurge)?;
                set_opt(&c, "gmax_residual", &mut sc.gmax_residual_turns)?;
                set_opt(&c, "hazard_order", &mut sc.hazard_order)?;
                set_opt(&c, "healing_wish", &mut sc.healing_wish)?;
                set_opt(&c, "wish_turns", &mut sc.wish_turns)?;
                set_opt(&c, "wish_hp", &mut sc.wish_hp)?;

                set_opt(&c, "fainted_count", &mut sc.fainted_count)?;
                set_opt(&c, "fainted_last_turn", &mut sc.fainted_last_turn)?;

                set_opt(&c, "future_turns", &mut sc.future_turns)?;
                set_opt(&c, "future_source", &mut sc.future_source)?;
                set_opt(&c, "future_move", &mut sc.future_move)?;
            }
            if let Some(mons) = opt::<Vec<Bound<'_, PyDict>>>(sd, "mons")? {
                if mons.len() != 4 {
                    return Err(err("load_state: each side's `mons` needs four entries"));
                }
                for (k, md) in mons.iter().enumerate() {
                    apply_mon(rules, &mut s.mons[k], md)?;
                }
            }
        }
        if let Some(rows) = opt::<Vec<(u8, u8, u8, u16, i16)>>(snapshot, "history")? {
            use engine_core::event::{Event, EventKind};
            for (kind, actor, target, subject, outcome) in rows {
                let kind = match kind {
                    1 => EventKind::Move, 2 => EventKind::Switch, 3 => EventKind::Faint, 4 => EventKind::StatusApplied,
                    5 => EventKind::BoostApplied, 6 => EventKind::Damage, 7 => EventKind::Heal,
                    _ => return Err(err(format!("history: event kind {kind}"))),
                };
                battle.history.push(Event { actor, kind, target, subject, outcome });
            }
        }
        battle.pending = engine_core::turn::check_pending(&battle);
        if battle.pending != Pending::Turn {
            return Err(err(format!("load_state: the snapshot isn't at a turn decision ({:?})", battle.pending)));
        }
        self.slots[index] = Some(Slot { battle, ctx, failed: false });
        Ok(())
    }



    fn dump(&self, index: usize) -> PyResult<String> {
        let slot = self.slots.get(index).and_then(|s| s.as_ref()).ok_or_else(|| err(format!("no battle in slot {index}")))?;
        let b = &slot.battle;
        Ok(format!("{:#?}", (&b.sides, &b.field, b.turn, &b.pending)))
    }





    fn inspect<'py>(&self, py: Python<'py>, index: usize) -> PyResult<Bound<'py, PyDict>> {
        use engine_data::{abilities_table, items_table, moves_table, species_table};
        let slot = self.slots.get(index).and_then(|s| s.as_ref()).ok_or_else(|| err(format!("no battle in slot {index}")))?;
        let b = &slot.battle;

        let item = |id: u16| if id == 0 || id as usize > items_table::ITEM_COUNT { "" } else { items_table::name(id) };
        let ability = |id: u16| if id == 0 || id as usize > abilities_table::ABILITY_COUNT { "" } else { abilities_table::name(id) };
        let mv = |id: u16| if id == 0 || id as usize > moves_table::MOVE_COUNT { "" } else { moves_table::name(id) };
        let out = PyDict::new(py);
        out.set_item("turn", b.turn)?;
        let (pending, forced, winner): (&str, [bool; 2], Option<u8>) = match b.pending {
            Pending::Turn => ("turn", [false, false], None),
            Pending::ForcedSwitch { side0, side1 } => ("forced", [side0, side1], None),
            Pending::Over { winner } => ("over", [false, false], winner),
        };
        out.set_item("pending", pending)?;
        out.set_item("forced", forced.to_vec())?;
        out.set_item("winner", winner)?;
        let f = PyDict::new(py);
        f.set_item("weather", format!("{:?}", b.field.weather))?;
        f.set_item("weather_turns", b.field.weather_turns)?;
        f.set_item("terrain", format!("{:?}", b.field.terrain))?;
        f.set_item("terrain_turns", b.field.terrain_turns)?;
        f.set_item("trick_room", b.field.trick_room_turns)?;
        f.set_item("gravity", b.field.gravity_turns)?;
        out.set_item("field", f)?;
        let sides = PyList::empty(py);
        for s in &b.sides {
            let sd = PyDict::new(py);
            sd.set_item("active", s.active.to_vec())?;
            sd.set_item("mega_used", s.mega_used)?;
            sd.set_item("z_used", s.z_used)?;
            sd.set_item("ultra_used", s.ultra_used)?;
            let c = PyDict::new(py);
            let sc = &s.side_conditions;
            c.set_item("tailwind", sc.tailwind_turns)?;
            c.set_item("reflect", sc.reflect_turns)?;
            c.set_item("light_screen", sc.light_screen_turns)?;
            c.set_item("aurora_veil", sc.aurora_veil_turns)?;
            c.set_item("safeguard", sc.safeguard_turns)?;
            sd.set_item("conds", c)?;
            let mons = PyList::empty(py);
            for m in &s.mons {
                let md = PyDict::new(py);
                md.set_item("species", species_table::get(m.species).name)?;
                md.set_item("item", item(m.item))?;
                md.set_item("ability", ability(m.ability))?;
                md.set_item("hp", m.hp)?;
                md.set_item("max_hp", m.max_hp)?;
                md.set_item("status", m.status as u8)?;
                md.set_item("boosts", m.boosts.to_vec())?;
                md.set_item("moves", m.moves.iter().map(|&id| mv(id)).collect::<Vec<_>>())?;
                md.set_item("pp", m.pp.to_vec())?;
                mons.append(md)?;
            }
            sd.set_item("mons", mons)?;
            sides.append(sd)?;
        }
        out.set_item("sides", sides)?;
        let events = PyList::empty(py);
        for e in b.history.iter() {
            let name = if e.kind == engine_core::event::EventKind::Move { mv(e.subject) } else { "" };
            events.append((e.kind as u8, e.actor, e.target, e.subject, e.outcome, name))?;
        }
        out.set_item("events", events)?;
        out.set_item("cursor", b.history.cursor())?;
        Ok(out)
    }


    fn drop_battles(&mut self, indices: Vec<usize>) -> PyResult<()> {
        for &i in &indices {
            *self.slots.get_mut(i).ok_or_else(|| err(format!("pool index {i} out of range")))? = None;
        }
        Ok(())
    }
}







fn keep_shown_hp(rules: &engine_core::rules::Rules, m: &mut engine_core::mon::Mon, old_hp: u16, old_max: u16, old_regen: u16) {
    if old_hp == 0 {
        return;
    }
    let (scale, up) = (rules.shown_hp_scale as u32, rules.shown_hp_rounds_up);
    let shown = |hp: u16, max: u16, regen: u16| -> u32 {
        let h = (hp - regen.min(hp.saturating_sub(1))) as u32;
        let (x, mx) = (h * scale, max.max(1) as u32);
        if up {
            let s = x.div_ceil(mx);
            if s == scale && h < max as u32 { s - 1 } else { s }
        } else {
            (x / mx).max(1)
        }
    };
    let target = shown(old_hp, old_max, old_regen);
    let new_max = m.max_hp.max(1) as u32;
    let regen = (old_regen as u32 * new_max / old_max as u32) as u16;
    let guess = ((old_hp as u32 * new_max + old_max as u32 / 2) / old_max as u32).clamp(1, new_max);
    m.regen_hidden = regen;
    if old_hp >= old_max {

        m.hp = new_max as u16;
        for d in 0..new_max {
            for r in [(regen as u32).checked_sub(d), Some(regen as u32 + d)].into_iter().flatten() {
                if r < new_max && shown(new_max as u16, new_max as u16, r as u16) == target {
                    m.regen_hidden = r as u16;
                    return;
                }
            }
        }
        return;
    }
    for d in 0..new_max {
        for h in [guess.checked_sub(d), Some(guess + d)].into_iter().flatten() {
            if (1..new_max).contains(&h) && shown(h as u16, new_max as u16, regen) == target {
                m.hp = h as u16;
                return;
            }
        }
    }
    m.hp = guess.min(new_max - 1).max(1) as u16;
}



fn item_shows(rules: &engine_core::rules::Rules, m: &engine_core::mon::Mon) -> bool {
    use engine_data::species_table::species_ids::{ZACIANCROWNED, ZAMAZENTACROWNED};
    m.item != 0
        && (m.mega.active
            || matches!(m.species, ZACIANCROWNED | ZAMAZENTACROWNED)
            || engine_core::mon::species_types_for(rules, m.species, m.ability, m.item)
                != engine_core::mon::species_types_for(rules, m.species, m.ability, 0))
}
fn req<'py, T: pyo3::conversion::FromPyObjectOwned<'py>>(d: &Bound<'py, PyDict>, key: &str) -> PyResult<T> {
    d.get_item(key)?.ok_or_else(|| err(format!("load_state: missing `{key}`")))?.extract::<T>().map_err(Into::into)
}


fn opt<'py, T: pyo3::conversion::FromPyObjectOwned<'py>>(d: &Bound<'py, PyDict>, key: &str) -> PyResult<Option<T>> {
    match d.get_item(key)? {
        Some(v) if !v.is_none() => Ok(Some(v.extract::<T>().map_err(Into::into)?)),
        _ => Ok(None),
    }
}

fn set_opt<'py, T: pyo3::conversion::FromPyObjectOwned<'py>>(d: &Bound<'py, PyDict>, key: &str, field: &mut T) -> PyResult<()> {
    if let Some(v) = opt::<T>(d, key)? {
        *field = v;
    }
    Ok(())
}









fn apply_mon(rules: &engine_core::rules::Rules, m: &mut engine_core::mon::Mon, d: &Bound<'_, PyDict>) -> PyResult<()> {
    use engine_core::mon::{mon_flags, volatile_flags};
    use engine_core::status::Status;

    if let Some(g) = opt::<String>(d, "gender")? {
        m.set_gender(match g.as_str() {
            "M" => engine_core::mon::Gender::Male,
            "F" => engine_core::mon::Gender::Female,
            "" | "N" => engine_core::mon::Gender::Genderless,
            _ => return Err(err(format!("load_state: gender {g:?}"))),
        });
    }



    if let Some(sp) = opt::<u16>(d, "transform")? {
        (m.pre_transform_species, m.base_moves, m.base_pp) = (m.species, m.moves, m.pp);
        m.flags.set(mon_flags::TRANSFORMED);
        m.species = sp;

        set_opt(d, "base_moves", &mut m.base_moves)?;
        set_opt(d, "base_pp", &mut m.base_pp)?;
    }
    if let Some(sp) = opt::<u16>(d, "species")? {
        if sp != m.species {
            if opt::<bool>(d, "mega")?.unwrap_or(false) {
                m.mega.active = true;
                m.mega.base_species = m.species;

                m.mega.base_ability = if m.base_ability != engine_core::ids::NONE_ID { m.base_ability } else { m.ability };
            }
            m.species = sp;
            let max_before = m.max_hp;
            m.recalc_stats(rules, rules.species_data(sp).base_stats);
            m.hp = m.hp.min(m.max_hp.max(max_before));
        }
    }
    if let Some(t) = opt::<[u8; 3]>(d, "types")? {
        m.types = t.map(|i| (i > 0).then(|| engine_data::type_chart::Type::from_index(i - 1)));
    }
    set_opt(d, "ability", &mut m.ability)?;
    set_opt(d, "base_ability", &mut m.base_ability)?;
    set_opt(d, "suppressed_ability", &mut m.suppressed_ability)?;
    set_opt(d, "item", &mut m.item)?;
    set_opt(d, "moves", &mut m.moves)?;
    set_opt(d, "pp", &mut m.pp)?;

    set_opt(d, "moves_revealed", &mut m.moves_revealed)?;

    set_opt(d, "transform_known", &mut m.transform_known)?;



    set_opt(d, "dynamax_level", &mut m.dynamax_level)?;
    if opt::<bool>(d, "gigantamax")?.unwrap_or(false) {
        m.flags.set(mon_flags::GIGANTAMAX);
    }
    if opt::<bool>(d, "dynamaxed")?.unwrap_or(false) {
        m.flags.set(mon_flags::DYNAMAXED);
        set_opt(d, "dynamax_turns", &mut m.dynamax_turns)?;
        m.base_max_hp = m.max_hp;
        if engine_core::items::pre_transform_species(m) != engine_data::species_table::species_ids::SHEDINJA {
            m.max_hp = (m.base_max_hp as f64 * (1.5 + m.dynamax_level as f64 * 0.05)).floor() as u16;
        }
    }

    if opt::<bool>(d, "dynamax_max_hp")?.unwrap_or(false)
        && engine_core::items::pre_transform_species(m) != engine_data::species_table::species_ids::SHEDINJA
    {
        m.base_max_hp = m.max_hp;
        m.max_hp = (m.base_max_hp as f64 * (1.5 + m.dynamax_level as f64 * 0.05)).floor() as u16;
    }
    if opt::<bool>(d, "last_move_max")?.unwrap_or(false) {
        m.flags.set(mon_flags::LAST_MOVE_MAX);
    }
    set_opt(d, "hp", &mut m.hp)?;
    if let Some(f) = opt::<f64>(d, "hp_frac")? {
        m.hp = if f <= 0.0 { 0 } else { ((f * m.max_hp as f64).round() as u16).clamp(1, m.max_hp) };
    }
    if opt::<bool>(d, "fainted")?.unwrap_or(m.hp == 0) {
        m.hp = 0;
        m.flags.set(mon_flags::FAINTED | mon_flags::FAINT_MESSAGED);
    }
    if opt::<bool>(d, "revealed")?.unwrap_or(false) {
        m.flags.set(mon_flags::REVEALED);
    }
    if let Some(st) = opt::<u8>(d, "status")? {
        m.status = match st {
            0 => Status::None, 1 => Status::Burn, 2 => Status::Freeze, 3 => Status::Paralysis, 4 => Status::Poison, 5 => Status::Toxic,
            6 => Status::Sleep, _ => return Err(err(format!("status {st}"))),
        };
    }
    set_opt(d, "status_counter", &mut m.status_counter)?;
    set_opt(d, "boosts", &mut m.boosts)?;
    set_opt(d, "turns_active", &mut m.turns_active)?;
    set_opt(d, "move_actions", &mut m.move_actions_since_switch_in)?;
    set_opt(d, "protect_counter", &mut m.protect_counter)?;
    set_opt(d, "sub_hp", &mut m.sub_hp)?;
    set_opt(d, "confusion", &mut m.confusion_turns)?;
    set_opt(d, "taunt", &mut m.taunt_turns)?;
    set_opt(d, "encore", &mut m.encore_turns)?;
    set_opt(d, "encore_move", &mut m.encore_move)?;
    set_opt(d, "disable", &mut m.disable_turns)?;
    set_opt(d, "disable_move", &mut m.disable_move)?;
    set_opt(d, "heal_block", &mut m.heal_block_turns)?;
    set_opt(d, "throat_chop", &mut m.throat_chop_turns)?;
    set_opt(d, "perish", &mut m.perish_turns)?;
    set_opt(d, "yawn", &mut m.yawn_turns)?;
    set_opt(d, "trap_turns", &mut m.trap_turns)?;
    set_opt(d, "trapped_by", &mut m.trapped_by)?;
    set_opt(d, "leech_seeder", &mut m.leech_seeder)?;
    set_opt(d, "charge_target", &mut m.charge_target)?;
    set_opt(d, "lock_move", &mut m.lock_move)?;
    set_opt(d, "lock_turns", &mut m.lock_turns)?;
    set_opt(d, "lock_true", &mut m.lock_true)?;
    set_opt(d, "choice_move", &mut m.choice_move)?;
    set_opt(d, "last_move", &mut m.last_move)?;

    m.charge_move = m.last_move;
    set_opt(d, "charge_move", &mut m.charge_move)?;
    set_opt(d, "last_move_target", &mut m.last_move_target)?;
    if let Some(conds) = opt::<Vec<(u8, u8)>>(d, "conds")? {
        for (id, turns) in conds {
            if id == 0 {
                return Err(err("load_state: condition id 0"));
            }
            m.volatiles.conds.set(id, turns);
        }
    }
    set_opt(d, "stockpile", &mut m.stockpile_layers)?;


    if let Some(t) = opt::<u8>(d, "tera_type")? {
        m.tera.tera_type = (t > 0).then(|| engine_data::type_chart::Type::from_index(t - 1));
    }
    if opt::<bool>(d, "tera")?.unwrap_or(false) {
        m.tera.active = true;
        if m.tera.typed() {
            let own = rules.species_data(m.species).types;
            m.tera.base_types = [own[0], own[1]];
        }
    }

    if let Some([sp, ab]) = opt::<[u16; 2]>(d, "forme_base")? {
        (m.mega.base_species, m.mega.base_ability) = (sp, ab);
    }
    set_opt(d, "stellar_boosted", &mut m.tera.stellar_boosted)?;
    set_opt(d, "times_attacked", &mut m.times_attacked)?;
    set_opt(d, "move_result", &mut m.move_result_this_turn)?;
    set_opt(d, "magnet_rise", &mut m.magnet_rise_turns)?;


    set_opt(d, "raw_stats", &mut m.stats)?;


    let split = match opt::<bool>(d, "stats_split")? {
        Some(v) => v,
        None => d.get_item("raw_stats")?.is_some_and(|v| !v.is_none()) && !m.flags.has(mon_flags::TRANSFORMED),
    };
    if split {
        m.flags.set(mon_flags::STATS_SPLIT);
    }


    if opt::<bool>(d, "power_trick")?.unwrap_or(false) {
        m.flags.set(mon_flags::POWER_TRICK);
    }
    if opt::<bool>(d, "last_move_z")?.unwrap_or(false) {
        m.flags.set(mon_flags::LAST_MOVE_Z);
    }
    if let Some(flags) = opt::<Vec<String>>(d, "flags")? {
        for f in flags {


            let mon_flag = match f.as_str() {
                "syrup_triggered" => Some(mon_flags::SYRUP_TRIGGERED),
                "commanding" => Some(mon_flags::COMMANDING),
                "trace_seek" => Some(mon_flags::TRACE_SEEK),
                "commanded" => Some(mon_flags::COMMANDED),
                "commanded_droopy" => Some(mon_flags::COMMANDED_DROOPY),
                "commanded_stretchy" => Some(mon_flags::COMMANDED_STRETCHY),
                "ngas_suppressed" => Some(mon_flags::NGAS_SUPPRESSED),
                "ngas_live" => Some(mon_flags::NGAS_LIVE),
                "booster_started" => Some(mon_flags::BOOSTER_STARTED),
                "bond_triggered" => Some(mon_flags::BOND_TRIGGERED),
                "unnerved" => Some(mon_flags::UNNERVED),
                _ => None,
            };
            if let Some(bit) = mon_flag {
                m.flags.set(bit);
                continue;
            }
            let bit = match f.as_str() {
                "charging" => volatile_flags::CHARGING,
                "mustrecharge" => volatile_flags::MUSTRECHARGE,
                "choice_locked" => volatile_flags::CHOICE_LOCKED,
                "imprison" => volatile_flags::IMPRISON,
                "gastro_acid" => volatile_flags::GASTRO_ACID,
                "item_consumed" => volatile_flags::ITEM_CONSUMED,
                "torment" => volatile_flags::TORMENT,
                "flashfire" => volatile_flags::FLASHFIRE,
                "glaiverush" => volatile_flags::GLAIVERUSH,
                "minimized" => volatile_flags::MINIMIZED,
                "charge" => volatile_flags::CHARGE,
                "invulnerable" => volatile_flags::INVULNERABLE,
                "protean" => volatile_flags::PROTEAN,
                "focusenergy" => volatile_flags::FOCUSENERGY,
                "dragoncheer" => volatile_flags::DRAGONCHEER,
                "dragoncheer_dragon" => volatile_flags::DRAGONCHEER_DRAGON,
                "smacked_down" => volatile_flags::SMACKED_DOWN,
                "aqua_ring" => volatile_flags::AQUA_RING,
                "ingrain" => volatile_flags::INGRAIN,
                "salt_cure" => volatile_flags::SALT_CURE,
                "cursed" => volatile_flags::CURSED,
                "destiny_bond" => volatile_flags::DESTINY_BOND,
                "no_retreat" => volatile_flags::NO_RETREAT,
                "gravity" => volatile_flags::GRAVITY,

                "stats_raised" => volatile_flags::STATS_RAISED,
                "stats_lowered" => volatile_flags::STATS_LOWERED,
                _ => return Err(err(format!("load_state: unknown mon flag {f:?}"))),
            };
            m.volatiles.set(bit);
        }
    }
    Ok(())
}




#[pyfunction(name = "lookup")]
fn lookup_id(kind: &str, name: &str) -> PyResult<u16> {
    Ok(match kind {
        "species" => lookup::species(name),
        "move" => lookup::move_id(name).filter(|&m| engine_data::moves_table::ported(m)),

        "zmove" => lookup::move_id(name),
        "item" => lookup::item(name),
        "ability" => lookup::ability(name),
        _ => return Err(err(format!("unknown lookup kind {kind:?}"))),
    }
    .unwrap_or(0))
}


fn rules_of(format: Option<&str>) -> PyResult<&'static engine_core::rules::Rules> {
    let f = match format {
        None => engine_core::rules::Format::ChampionsMC,
        Some(id) => engine_core::rules::Format::from_id(id).ok_or_else(|| err(format!("unknown format {id:?}")))?,
    };
    Ok(engine_core::rules::Rules::of(f))
}





#[pyfunction]
#[pyo3(signature = (species, format=None, ability=None, item=0))]
fn species_types(species: u16, format: Option<&str>, ability: Option<u16>, item: u16) -> PyResult<(i32, i32)> {
    let rules = rules_of(format)?;
    let t = match ability {
        Some(a) => {
            let t = engine_core::mon::species_types_for(rules, species, a, item);
            [t[0], t[1]]
        }
        None => rules.species_data(species).types,
    };
    Ok((t[0].map_or(0, |t| t as i32 + 1), t[1].map_or(0, |t| t as i32 + 1)))
}



#[pyfunction]
#[pyo3(signature = (set, species, format=None))]
fn set_stats(set: &Bound<'_, PyDict>, species: u16, format: Option<&str>) -> PyResult<[u16; 6]> {
    let rules = rules_of(format)?;
    let mut parsed = parse_set(set, rules)?;
    parsed.species = species;
    let mon = engine_core::team::build_mon_in(rules, &parsed);
    Ok([mon.max_hp, mon.stats[0], mon.stats[1], mon.stats[2], mon.stats[3], mon.stats[4]])
}








#[pyfunction]
fn dex_tables<'py>(py: Python<'py>) -> (Bound<'py, numpy::PyArray2<f32>>, Bound<'py, numpy::PyArray2<f32>>) {
    use engine_data::moves_table::{self, Accuracy, Category, ChoiceTarget, FieldEffect, MoveTarget, SecondaryEffect};
    use engine_data::species_table;
    let frac = |r: Option<(u32, u32)>| r.map_or(0.0, |(a, b)| a as f32 / b.max(1) as f32);
    let mut moves: Vec<Vec<f32>> = vec![Vec::new()];
    for id in 1..=moves_table::MOVE_COUNT as u16 {
        let m = moves_table::get(id);
        let mut f = vec![m.base_power as f32 / 150.0, (m.base_power > 0) as u8 as f32];
        match m.accuracy {
            Accuracy::AlwaysHits => f.extend([1.0, 1.0]),
            Accuracy::Percent(p) => f.extend([p as f32 / 100.0, 0.0]),
        }
        let mut ty = [0f32; 19];
        ty[m.move_type as usize] = 1.0;
        f.extend(ty);
        f.extend(match m.category { Category::Physical => [1.0, 0.0, 0.0], Category::Special => [0.0, 1.0, 0.0], Category::Status => [0.0, 0.0, 1.0] });
        f.extend([m.priority as f32 / 4.0, (m.priority > 0) as u8 as f32, (m.priority < 0) as u8 as f32]);
        let mut tg = [0f32; 8];
        tg[match m.target {
            MoveTarget::Normal => 0, MoveTarget::Self_ => 1, MoveTarget::AllAdjacent => 2, MoveTarget::AllAdjacentFoes => 3,
            MoveTarget::All => 4, MoveTarget::AllySide => 5, MoveTarget::FoeSide => 6, MoveTarget::AdjacentAlly => 7,
        }] = 1.0;
        f.extend(tg);
        let mut ct = [0f32; 5];
        ct[match m.choice_target {
            ChoiceTarget::None => 0, ChoiceTarget::Adjacent => 1, ChoiceTarget::AdjacentFoe => 2, ChoiceTarget::AdjacentAlly => 3, ChoiceTarget::AllyOrSelf => 4,
        }] = 1.0;
        f.extend(ct);
        f.extend([engine_core::mon::max_pp(id) as f32 / 40.0, (m.crit_ratio > 1) as u8 as f32, m.will_crit as u8 as f32]);
        for flag in [m.blocked_by_protect, m.contact, m.sound, m.reflectable, m.breaks_protect, m.charge, m.recharge, m.punch, m.slicing, m.pulse,
                     m.bullet, m.heal_flag, m.powder, m.bite, m.self_switch] {
            f.push(flag as u8 as f32);
        }
        f.extend([m.multihit_max as f32 / 5.0, frac(m.recoil), frac(m.drain), frac(m.heal)]);
        f.extend(m.self_boosts.unwrap_or([0; 7]).map(|b| b as f32 / 2.0));
        f.extend(m.boosts.unwrap_or([0; 7]).map(|b| b as f32 / 2.0));
        let mut st = [0f32; 6];
        if let Some(s) = m.status {
            st[s as usize - 1] = 1.0;
        }
        f.extend(st);
        let mut sec = [0f32; 6];
        if let Some(x) = m.secondary {
            sec[0] = x.chance as f32 / 100.0;
            sec[1 + match x.effect {
                SecondaryEffect::Status(_) => 0, SecondaryEffect::Boosts(_) => 1, SecondaryEffect::Flinch => 2,
                SecondaryEffect::SelfBoosts(_) => 3, SecondaryEffect::RandomStatus(_) => 4,
            }] = 1.0;
        }
        f.extend(sec);
        let mut fe = [0f32; 20];


        let unfeatured = |e: FieldEffect| {
            matches!(
                e,
                FieldEffect::FairyLock
                    | FieldEffect::Safeguard
                    | FieldEffect::MagicRoom
                    | FieldEffect::WonderRoom
                    | FieldEffect::Mist
                    | FieldEffect::LuckyChant
                    | FieldEffect::MudSport
                    | FieldEffect::WaterSport
                    | FieldEffect::IonDeluge
            )
        };
        if let Some(e) = m.field_effect.filter(|&e| !unfeatured(e)) {
            fe[match e {

                FieldEffect::WideGuard | FieldEffect::CraftyShield | FieldEffect::MatBlock => 0, FieldEffect::QuickGuard => 1, FieldEffect::Rain => 2, FieldEffect::Sun => 3, FieldEffect::Sand => 4,
                FieldEffect::Snow | FieldEffect::Hail => 5, FieldEffect::Tailwind => 6, FieldEffect::TrickRoom => 7, FieldEffect::Reflect => 8, FieldEffect::LightScreen => 9,
                FieldEffect::AuroraVeil => 10, FieldEffect::StealthRock => 11, FieldEffect::Spikes => 12, FieldEffect::ToxicSpikes => 13,
                FieldEffect::StickyWeb => 14, FieldEffect::ElectricTerrain => 15, FieldEffect::GrassyTerrain => 16, FieldEffect::MistyTerrain => 17,
                FieldEffect::PsychicTerrain => 18, FieldEffect::Gravity => 19, FieldEffect::FairyLock | FieldEffect::Safeguard | FieldEffect::MagicRoom | FieldEffect::WonderRoom | FieldEffect::Mist
                | FieldEffect::LuckyChant | FieldEffect::MudSport | FieldEffect::WaterSport | FieldEffect::IonDeluge => unreachable!(),
            }] = 1.0;
        }
        f.extend(fe);
        moves.push(f);
    }
    let width = moves[1].len();
    moves[0] = vec![0.0; width];
    let mut species: Vec<Vec<f32>> = vec![Vec::new()];
    for id in 1..=species_table::SPECIES_COUNT as u16 {
        let s = species_table::get(id);
        let mut f: Vec<f32> = s.base_stats.iter().map(|&b| b as f32 / 150.0).collect();
        let mut ty = [0f32; 19];
        for t in s.types.iter().flatten() {
            ty[*t as usize] = 1.0;
        }
        f.extend(ty);
        f.push(s.is_mega as u8 as f32);
        f.push((s.weight_hg as f32 / 10.0 + 1.0).ln() / 7.0);
        species.push(f);
    }
    species[0] = vec![0.0; species[1].len()];
    (numpy::PyArray2::from_vec2(py, &moves).expect("rectangular"), numpy::PyArray2::from_vec2(py, &species).expect("rectangular"))
}


#[pyfunction]
fn species_ability(species: u16) -> u16 {
    engine_data::species_table::get(species).abilities[0]
}


#[pyfunction]
fn move_target(move_id: u16) -> String {
    format!("{:?}", engine_data::moves_table::get(move_id).target).to_lowercase()
}



#[pyfunction]
fn move_category(move_id: u16) -> String {
    format!("{:?}", engine_data::moves_table::get(move_id).category).to_lowercase()
}



#[pyfunction]
fn move_choice_target(move_id: u16) -> String {
    format!("{:?}", engine_data::moves_table::get(move_id).choice_target).to_lowercase()
}


#[pyfunction]
#[pyo3(signature = (move_id, format=None))]
fn max_pp(move_id: u16, format: Option<&str>) -> PyResult<u8> {
    Ok(rules_of(format)?.max_pp(move_id))
}



#[pyfunction]
#[pyo3(signature = (item, species, moves=Vec::new(), format=None))]
fn mega_forme(item: u16, species: u16, moves: Vec<u16>, format: Option<&str>) -> PyResult<u16> {
    Ok(engine_core::items::mega_forme(item, species, &moves, rules_of(format)?.dragon_ascent_mega).unwrap_or(0))
}



#[pyfunction]
#[pyo3(signature = (item, species, moves, format=None))]
fn z_capable(item: u16, species: u16, moves: Vec<u16>, format: Option<&str>) -> PyResult<bool> {
    Ok(engine_obs::z_capable_sheet(rules_of(format)?, item, species, &moves))
}



#[pyfunction]
#[pyo3(signature = (item, species, base_move, format=None))]
fn z_move_of(item: u16, species: u16, base_move: u16, format: Option<&str>) -> PyResult<u16> {
    Ok(engine_obs::z_move_of_sheet(rules_of(format)?, item, species, base_move).unwrap_or(0))
}



#[pyfunction]
fn z_base_move(z_move: u16) -> u16 {
    use engine_data::z_table::{Crystal, Z_CRYSTALS};
    Z_CRYSTALS
        .iter()
        .find_map(|&(_, c)| match c {
            Crystal::Signature { base_move, z_move: z, .. } if z == z_move && z != 0 => Some(base_move),
            _ => None,
        })
        .unwrap_or(0)
}


fn add_constants(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("OBS_VERSION", engine_obs::OBS_VERSION)?;


    m.add("ENGINE_BUILD", option_env!("VGC_ENGINE_BUILD"))?;
    m.add("FIELD_FEATURES", engine_obs::FIELD_FEATURES)?;
    m.add("MON_TOKENS", engine_obs::MON_TOKENS)?;
    m.add("MON_IDS", engine_obs::MON_IDS)?;
    m.add("MON_FEATURES", engine_obs::MON_FEATURES)?;
    m.add("HISTORY_LEN", engine_obs::HISTORY_LEN)?;
    m.add("EVENT_FIELDS", engine_obs::EVENT_FIELDS)?;
    m.add("SPECIES_VOCAB", engine_obs::SPECIES_VOCAB)?;
    m.add("ITEM_VOCAB", engine_obs::ITEM_VOCAB)?;
    m.add("ABILITY_VOCAB", engine_obs::ABILITY_VOCAB)?;
    m.add("MOVE_VOCAB", engine_obs::MOVE_VOCAB)?;
    m.add("TYPE_VOCAB", engine_obs::TYPE_VOCAB)?;
    m.add("SLOT_ACTIONS", legal::SLOT_ACTIONS)?;
    m.add("SWITCH_BASE", legal::SWITCH_BASE)?;
    m.add("PASS_ACTION", legal::PASS_ACTION)?;
    m.add("ROSTER_SIZE", ROSTER_SIZE)?;
    m.add("BROUGHT_SIZE", BROUGHT_SIZE)?;
    Ok(())
}




#[cfg(feature = "alloc-count")]
#[pyfunction]
fn alloc_counts(py: Python<'_>) -> PyResult<Bound<'_, PyDict>> {
    use std::sync::atomic::Ordering::Relaxed;
    let d = PyDict::new(py);
    for (k, name) in alloc_count::KINDS.iter().enumerate() {
        d.set_item(*name, (alloc_count::COUNTS[k].load(Relaxed), alloc_count::CALLS[k].load(Relaxed)))?;
    }
    Ok(d)
}


#[cfg(feature = "alloc-count")]
#[pyfunction]
#[pyo3(signature = (trace=false))]
fn alloc_reset(trace: bool) {
    use std::sync::atomic::Ordering::Relaxed;
    for k in 0..4 {
        alloc_count::COUNTS[k].store(0, Relaxed);
        alloc_count::CALLS[k].store(0, Relaxed);
    }
    if let Ok(mut m) = alloc_count::SITES.lock() {
        m.clear();
    }
    alloc_count::TRACE.store(trace, Relaxed);
}


#[cfg(feature = "alloc-count")]
#[pyfunction]
fn alloc_sites() -> Vec<(String, u64)> {
    let mut v: Vec<(String, u64)> = alloc_count::SITES.lock().map(|m| m.iter().map(|(k, c)| (k.clone(), *c)).collect()).unwrap_or_default();
    v.sort_by(|a, b| b.1.cmp(&a.1));
    v
}

#[pymodule]
fn vgc_engine(m: &Bound<'_, PyModule>) -> PyResult<()> {
    #[cfg(feature = "alloc-count")]
    {
        m.add_function(wrap_pyfunction!(alloc_counts, m)?)?;
        m.add_function(wrap_pyfunction!(alloc_reset, m)?)?;
        m.add_function(wrap_pyfunction!(alloc_sites, m)?)?;
    }
    m.add_class::<BattlePool>()?;
    m.add_function(wrap_pyfunction!(lookup_id, m)?)?;
    m.add_function(wrap_pyfunction!(species_types, m)?)?;
    m.add_function(wrap_pyfunction!(max_pp, m)?)?;
    m.add_function(wrap_pyfunction!(species_ability, m)?)?;
    m.add_function(wrap_pyfunction!(move_target, m)?)?;
    m.add_function(wrap_pyfunction!(move_category, m)?)?;
    m.add_function(wrap_pyfunction!(set_stats, m)?)?;
    m.add_function(wrap_pyfunction!(move_choice_target, m)?)?;
    m.add_function(wrap_pyfunction!(dex_tables, m)?)?;
    m.add_function(wrap_pyfunction!(mega_forme, m)?)?;
    m.add_function(wrap_pyfunction!(z_capable, m)?)?;
    m.add_function(wrap_pyfunction!(z_base_move, m)?)?;
    m.add_function(wrap_pyfunction!(z_move_of, m)?)?;
    add_constants(m)
}
