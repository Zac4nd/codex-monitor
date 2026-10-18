import St from 'gi://St';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

export default class CodexMonitorExtension extends Extension {
    enable() {
        this._indicator = new PanelMenu.Button(0.0, 'Codex Monitor', false);
        this._label = new St.Label({text: '● Codex …', y_align: 2});
        this._indicator.add_child(this._label);
        Main.panel.addToStatusArea(this.uuid, this._indicator, 0, 'right');
        this._busy = false;
        this._closed = false;
        this._refresh();
        this._timer = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 2, () => {
            this._refresh();
            return GLib.SOURCE_CONTINUE;
        });
    }

    _run(command, args = []) {
        const executable = GLib.build_filenamev([this.path, 'backend.py']);
        const argv = ['/usr/bin/python3', executable, command, ...args];
        return new Promise((resolve, reject) => {
            try {
                const process = Gio.Subprocess.new(argv,
                    Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE);
                process.communicate_utf8_async(null, null, (source, result) => {
                    try {
                        const [, output] = source.communicate_utf8_finish(result);
                        const data = JSON.parse(output);
                        if (!source.get_successful() || data.error)
                            reject(new Error(data.error || 'backend error'));
                        else
                            resolve(data);
                    } catch (e) { reject(e); }
                });
            } catch (e) { reject(e); }
        });
    }

    _refresh() {
        if (this._busy || this._closed)
            return;
        this._busy = true;
        this._run('list').then(data => {
            if (!this._closed)
                this._render(data);
        }).catch(e => {
            if (!this._closed) {
                this._label.set_text('● Codex ?');
                this._label.set_style('color: #e5ad52;');
                logError(e, 'Codex Monitor');
            }
        }).finally(() => { this._busy = false; });
    }

    _action(command, key) {
        this._run(command, key ? [key] : []).then(() => {
            this._refresh();
        }).catch(e => logError(e, 'Codex Monitor'));
    }

    _render(data) {
        const active = data.active || [];
        const ignored = data.ignored || [];
        const count = active.length;
        this._label.set_text(`● Codex ${count}` + (ignored.length ? ` (−${ignored.length})` : ''));
        this._label.set_style(`color: ${count ? '#ff7777' : '#6ee5a2'};`);
        const menu = this._indicator.menu;
        menu.removeAll();
        const title = new PopupMenu.PopupMenuItem(
            `${count} attivi · ${ignored.length} ignorati`, {reactive: false});
        menu.addMenuItem(title);
        menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        if (!count && !ignored.length) {
            menu.addMenuItem(new PopupMenu.PopupMenuItem('Nessuna esecuzione Codex', {reactive: false}));
        }
        for (const proc of [...active, ...ignored]) {
            const prefix = proc.ignored ? '⛔' : '●';
            const min = Math.floor(proc.seconds / 60);
            const sec = String(proc.seconds % 60).padStart(2, '0');
            const line = `${prefix} ${proc.project} · PID ${proc.pid} · ${min}:${sec}`;
            const item = new PopupMenu.PopupMenuItem(line);
            if (proc.ignored)
                item.label.set_style('color: #ff7777;');
            item.label.set_tooltip_text?.(proc.command);
            item.connect('activate', () => this._action(proc.ignored ? 'restore' : 'ignore', proc.identity));
            menu.addMenuItem(item);
        }
        if (ignored.length) {
            menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
            const restore = new PopupMenu.PopupMenuItem('Ripristina tutti gli ignorati');
            restore.connect('activate', () => this._action('restore-all'));
            menu.addMenuItem(restore);
        }
    }

    disable() {
        this._closed = true;
        if (this._timer) {
            GLib.Source.remove(this._timer);
            this._timer = null;
        }
        this._indicator?.destroy();
        this._indicator = null;
    }
}
