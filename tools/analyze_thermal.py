"""Saved-board QuickTherm screen using reviewed cycle-average KERO heat inputs.
Requires an existing KiCad-native Python and WayriCAD source; never provisions.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'analysis' / 'thermal'
POWER = ROOT / 'evidence' / 'analysis' / 'power-budget.json'
STACKUP = [
    {'name': 'F.Cu', 'z_mm': .0175, 'thickness_mm': .035},
    {'name': 'B.Cu', 'z_mm': 1.5825, 'thickness_mm': .035},
]
LIMITS = [
    'Illustrative steady board-temperature screen; no measured thermal calibration or qualification.',
    'Cycle-average nominal 3 V losses; not switching or startup temperatures.',
    'LED electrical power is conservatively deposited as heat; optical output is unknown.',
    'All selected power enters board contact proxies; package-air cooling is omitted.',
    'No package RthetaJB or internal component model: all junction temperatures remain unknown.',
    'Unspecified saved stackup is replaced only in the geometry extraction call by explicit 35 um copper layers within a 1.6 mm span.',
    'Homogeneous isotropic FR4 k=0.3 W/m/K and copper k=385 W/m/K are illustrative assumptions, not material certification.',
    'Two exposed faces, natural-convection h=5 W/m2/K, emissivity=0, ambient=25 C; radiation omitted conservatively for heat rejection.',
    'Cell internal heat, contact resistance, capacitor loss and copper Joule heat are excluded; cell internal resistance is unknown.',
    'No enclosure, battery/package shadowing or mechanical heat sinks; contact sources use producer footprint-area proxies.',
    'Grid comparison establishes numerical sensitivity only; subcell sources and barrel contacts remain approximate.',
]

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8', newline='\n')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wayricad-source', required=True, type=Path)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    for name in ['coarse.results.json', 'nominal.results.json', 'nominal.html', 'nominal.json', 'nominal.pocket-kivi.json']:
        if (OUT / name).exists():
            raise FileExistsError('Preserve previous output before rerunning: ' + name)
    # Only bounded task-owned scratch on D:, without modifying shared caches.
    scratch = OUT / '.scratch'
    scratch.mkdir(exist_ok=True)
    os.environ['MPLCONFIGDIR'] = str(scratch / 'matplotlib')
    os.environ['TEMP'] = os.environ['TMP'] = str(scratch)
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    os.environ['MPLBACKEND'] = 'Agg'
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(args.wayricad_source.resolve()))
    from quick_therm_plugin import service, thermal_geometry, report
    from wayricad_runtime.pocket_report import evidence_context
    from wayricad_runtime.project_results import save_result, load_result
    board = ROOT / 'KERO.kicad_pcb'
    before = digest(board)
    power = json.loads(POWER.read_text(encoding='utf-8'))
    if power['source_sha256']['KERO.kicad_pcb'] != before:
        raise ValueError('Power budget does not describe this saved PCB.')
    for filename, expected in power['source_sha256'].items():
        if digest(ROOT / filename) != expected:
            raise ValueError('Power budget source changed: ' + filename)
    losses = power['nominal']['losses']
    sources = {f'R{i}': {'power_w': losses[f'R{i}_W']} for i in range(1, 8)}
    sources.update(U1={'power_w': losses['U1A_W'] + losses['U1B_W']},
                   D1={'power_w': losses['D1_electrical_W']},
                   D2={'power_w': losses['D2_electrical_W']})
    total = sum(row['power_w'] for row in sources.values())
    if abs(total - power['nominal']['battery_terminal_power_W']) > 1e-12:
        raise ValueError('Heat-source sum does not match the reviewed nominal power.')
    config = dict(environment='air', ambient_c=25., input_mode='manual',
                  references=list(sources), manual_values=sources, board_power_only=True,
                  thermal_model_kind='multilayer', thermal_network_settings=dict(
                      mesh_mode='manual', grid_cells_long_axis=40, dielectric_k_w_mk=.3,
                      copper_k_w_mk=385., via_plating_mm=.025, board_h_w_m2k=5.,
                      board_emissivity=0., board_airflow_m_s=0., copper_raster_mode='area_face',
                      barrel_contact_mode='annulus_stencil', source_refinement_factor=1))
    write('coarse.config.json', config)
    fine_config = json.loads(json.dumps(config))
    fine_config['thermal_network_settings']['grid_cells_long_axis'] = 80
    write('nominal.config.json', fine_config)
    write('model-inputs.json', dict(power_budget_file=POWER.relative_to(ROOT).as_posix(),
        power_budget_sha256=digest(POWER), source_sha256=before, stackup_override=STACKUP,
        sources_W={key: row['power_w'] for key, row in sources.items()}, total_heat_W=total,
        limitations=LIMITS, adapter='thermal_geometry.stackup delegates to the original shared stackup parser with explicit override; no source or solver modification'))
    capacity_before = {drive: shutil.disk_usage(drive).free / 2**30 for drive in ['C:/', 'D:/']}
    original_stackup = thermal_geometry.stackup
    def explicit_stackup(board, api, source_text=None):
        return original_stackup(board, api, source_text, override=STACKUP)
    thermal_geometry.stackup = explicit_stackup
    summaries = []
    try:
        for label, selected in [('coarse', config), ('nominal', fine_config)]:
            request = dict(action='quick_therm', board_path=str(board), **selected)
            result = service.execute(request)
            if digest(board) != before or result['source_sha256'] != before:
                raise ValueError('Saved board changed during the thermal solve.')
            result['kero_model_inputs'] = json.loads((OUT / 'model-inputs.json').read_text())
            result['kero_model_inputs'].pop('source_sha256')
            result['quick_therm']['assumptions'].extend(LIMITS)
            network = result['thermal_network']
            if network['status'] != 'converged':
                raise ValueError('QuickTherm heat balance did not converge.')
            if any(row.get('junction_c') is not None for row in network['components']):
                raise ValueError('Unexpected junction result without a declared package path.')
            evidence = evidence_context(result, tool='QuickTherm', module_file=service.__file__,
                package='quick_therm_plugin', units={'ambient_c':'C','temperature_c':'C','power_w':'W'},
                coordinate_frame='KiCad PCB XY in mm', z_basis='front-depth')
            saved = save_result(ROOT, 'quick-therm', result, pocket_kivi=evidence,
                destination=OUT / (label + '.results.json'))
            loaded = load_result(ROOT, OUT / (label + '.results.json'), plugin='quick-therm', chosen=True)
            summaries.append(dict(name=label, grid=selected['thermal_network_settings']['grid_cells_long_axis'],
                mesh=network['mesh'], heat_balance=network['heat_balance'],
                layers=[{key:value for key,value in row.items() if key in ('id','name','z_mm','sampled_min_c','sampled_max_c','sampled_max_cell')} for row in network['layers']],
                components=network['components'], native_load_receipt=loaded['receipt']))
            print(label, json.dumps(network['heat_balance']), flush=True)
            if label == 'nominal':
                # Producer report emits readable HTML, original full JSON and portable companion.
                report.write_diagnostic_report(OUT / 'nominal.html', result, pocket_kivi=True)
    finally:
        thermal_geometry.stackup = original_stackup
    # Compare the actual board-site and source-peak results across both grids.
    a = {row['reference']: row for row in summaries[0]['components']}
    b = {row['reference']: row for row in summaries[1]['components']}
    changes = {ref: {key: abs(b[ref][key] - a[ref][key]) for key in ['board_site_c','source_peak_c']
                    if a[ref].get(key) is not None and b[ref].get(key) is not None} for ref in a}
    write('summary.json', dict(producer='WayriCAD QuickTherm 4.5.0', source_sha256=before,
        heat_input_W=total, studies=summaries, component_grid_changes_C=changes,
        maximum_component_change_C=max(v for row in changes.values() for v in row.values()),
        convergence_scope='Two-grid sensitivity comparison; no physical/package qualification or local contact-resolution guarantee.',
        capacity_before_GiB=capacity_before,
        capacity_after_GiB={drive:shutil.disk_usage(drive).free/2**30 for drive in ['C:/','D:/']},
        limitations=LIMITS))
    for font_cache in (scratch / 'matplotlib').glob('fontlist-v*.json'):
        if font_cache.is_file() and font_cache.resolve().is_relative_to(scratch.resolve()):
            font_cache.unlink()
    for folder in [scratch / 'matplotlib', scratch]:
        if folder.is_dir() and not any(folder.iterdir()):
            folder.rmdir()
    print('Thermal results, native reload and source preservation verified.', flush=True)

if __name__ == '__main__':
    main()
