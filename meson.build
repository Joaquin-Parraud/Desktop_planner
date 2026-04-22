project(
  'desktop-planner',
  version: '0.1.0',
  meson_version: '>= 0.59.0',
  default_options: ['warning_level=2'],
)

py = import('python').find_installation('python3')

py_sources = [
  'src/desktop_planner/__init__.py',
  'src/desktop_planner/__main__.py',
  'src/desktop_planner/database.py',
  'src/desktop_planner/dates.py',
  'src/desktop_planner/mcp_server.py',
  'src/desktop_planner/models.py',
  'src/desktop_planner/notifications.py',
  'src/desktop_planner/paths.py',
  'src/desktop_planner/ui.py',
]

py.install_sources(py_sources, subdir: 'desktop_planner')

# Launcher script — bake the module install path so the script finds
# desktop_planner regardless of where meson placed it on this distro.
configure_file(
  input: 'packaging/desktop-planner.in',
  output: 'desktop-planner',
  configuration: {
    'PYTHON': py.full_path(),
    'MODULE_DIR': py.get_install_dir(pure: true),
  },
  install: true,
  install_dir: get_option('bindir'),
  install_mode: 'rwxr-xr-x',
)

# Desktop entry & icon
install_data(
  'packaging/org.example.DesktopPlanner.desktop',
  install_dir: join_paths(get_option('datadir'), 'applications'),
)

install_data(
  'packaging/org.example.DesktopPlanner.svg',
  install_dir: join_paths(get_option('datadir'), 'icons', 'hicolor', 'scalable', 'apps'),
)
