import re

css = open(r'D:\Users\bing\Desktop\AIDBTools\icons\remixicon.css', 'r', encoding='utf-8').read()

pattern = r'\.ri-([a-z0-9-]+):before\s*\{\s*content:\s*"([^"]+)"'
raw_icons = dict(re.findall(pattern, css))

# Extract hex code
icons = {}
for name, content in raw_icons.items():
    # content is like "\\ea01" in Python string
    # strip all backslashes then get trailing hex
    cleaned = content.replace('\\', '')
    hex_match = re.search(r'([0-9a-f]{4,6})$', cleaned)
    if hex_match:
        icons[name] = hex_match.group(1)

# Build the full mapping we need
needed = {
    # Database & Connection
    'database': 'database-2-line',
    'database_fill': 'database-2-fill',
    'server': 'server-line',
    'server_fill': 'server-fill',
    'plug': 'plug-line',
    'plug_fill': 'plug-fill',
    'link': 'link-m',
    'link_unlink': 'link-unlink',
    'links': 'links-line',
    'links_fill': 'links-fill',
    
    # Actions - Play/Run
    'play': 'play-line',
    'play_fill': 'play-fill',
    'play_circle': 'play-circle-line',
    'play_circle_fill': 'play-circle-fill',
    'send': 'send-plane-line',
    'send_fill': 'send-plane-fill',
    'arrow_right': 'arrow-right-s-line',
    'arrow_down': 'arrow-down-s-line',
    'arrow_up': 'arrow-up-s-line',
    'arrow_left': 'arrow-left-s-line',
    
    # Actions - Code
    'code': 'code-line',
    'code_fill': 'code-fill',
    'code_box': 'code-box-line',
    'code_s_slash': 'code-s-slash-line',
    'terminal': 'terminal-box-line',
    'terminal_line': 'terminal-line',
    'braces': 'braces-line',
    
    # Actions - File IO
    'download': 'download-line',
    'download_fill': 'download-fill',
    'download_2': 'download-2-line',
    'upload': 'upload-line',
    'upload_fill': 'upload-fill',
    'upload_2': 'upload-2-line',
    'import': 'import-line',
    'import_fill': 'import-fill',
    'export': 'export-line',
    'export_fill': 'export-fill',
    'file_upload': 'file-upload-line',
    'file_upload_fill': 'file-upload-fill',
    'file_download': 'file-download-line',
    'file_download_fill': 'file-download-fill',
    
    # Actions - Edit
    'copy': 'file-copy-line',
    'copy_fill': 'file-copy-fill',
    'clipboard': 'clipboard-line',
    'clipboard_fill': 'clipboard-fill',
    'paste': 'clipboard-fill',
    'cut': 'scissors-line',
    'cut_fill': 'scissors-fill',
    'undo': 'arrow-go-back-line',
    'redo': 'arrow-go-forward-line',
    'eraser': 'eraser-line',
    'find_replace': 'find-replace-line',
    
    # Actions - CRUD
    'add': 'add-line',
    'add_fill': 'add-fill',
    'add_circle': 'add-circle-line',
    'add_circle_fill': 'add-circle-fill',
    'add_box': 'add-box-line',
    'add_box_fill': 'add-box-fill',
    'subtract': 'subtract-line',
    'delete': 'delete-bin-line',
    'delete_fill': 'delete-bin-fill',
    'delete_back': 'delete-back-2-line',
    'edit': 'edit-line',
    'edit_fill': 'edit-fill',
    'edit_box': 'edit-box-line',
    'check': 'check-line',
    'check_fill': 'check-fill',
    'check_double': 'check-double-line',
    'close': 'close-line',
    'close_fill': 'close-fill',
    'close_circle': 'close-circle-line',
    'close_circle_fill': 'close-circle-fill',
    
    # Actions - View
    'search': 'search-line',
    'search_fill': 'search-fill',
    'search_2': 'search-2-line',
    'search_eye': 'search-eye-line',
    'filter': 'filter-line',
    'filter_fill': 'filter-fill',
    'filter_2': 'filter-2-line',
    'filter_2_fill': 'filter-2-fill',
    'filter_3': 'filter-3-line',
    'filter_3_fill': 'filter-3-fill',
    'sort_asc': 'sort-asc',
    'sort_desc': 'sort-desc',
    'eye': 'eye-line',
    'eye_fill': 'eye-fill',
    'eye_off': 'eye-off-line',
    'zoom_in': 'zoom-in-line',
    'zoom_out': 'zoom-out-line',
    'focus': 'focus-3-line',
    'fullscreen': 'fullscreen-line',
    'fullscreen_exit': 'fullscreen-exit-line',
    
    # Actions - Layout
    'expand_down': 'arrow-down-s-line',
    'expand_up': 'arrow-up-s-line',
    'expand_left': 'expand-left-line',
    'expand_right': 'expand-right-line',
    'contract_left': 'contract-left-line',
    'contract_right': 'contract-right-line',
    'layout_right': 'layout-right-line',
    'layout_left': 'layout-left-line',
    'layout_bottom': 'layout-bottom-line',
    'layout_top': 'layout-top-line',
    'layout_column': 'layout-column-line',
    'layout_grid': 'layout-grid-line',
    'layout_row': 'layout-row-line',
    'menu': 'menu-line',
    'menu_fill': 'menu-fill',
    'more': 'more-line',
    'more_fill': 'more-fill',
    'more_2': 'more-2-fill',
    'apps': 'apps-line',
    'apps_fill': 'apps-fill',
    'sidebar': 'sidebar-unfold-line',
    
    # AI & Chat
    'robot': 'robot-line',
    'robot_fill': 'robot-fill',
    'chat': 'chat-1-line',
    'chat_fill': 'chat-1-fill',
    'chat_smile': 'chat-smile-line',
    'chat_smile_fill': 'chat-smile-fill',
    'chat_new': 'chat-new-line',
    'chat_new_fill': 'chat-new-fill',
    'sparkling': 'sparkling-line',
    'sparkling_fill': 'sparkling-fill',
    'sparkling_2': 'sparkling-2-fill',
    'magic': 'magic-line',
    'magic_fill': 'magic-fill',
    
    # Status & Feedback
    'info': 'information-line',
    'info_fill': 'information-fill',
    'warning': 'alert-line',
    'warning_fill': 'alert-fill',
    'error': 'error-warning-line',
    'error_fill': 'error-warning-fill',
    'success': 'checkbox-circle-line',
    'success_fill': 'checkbox-circle-fill',
    'loader': 'loader-4-line',
    'loader_fill': 'loader-4-fill',
    'notification': 'notification-line',
    'notification_fill': 'notification-fill',
    'notification_2': 'notification-2-line',
    'notification_2_fill': 'notification-2-fill',
    
    # Navigation
    'home': 'home-5-line',
    'home_fill': 'home-5-fill',
    'arrow_right_line': 'arrow-right-line',
    'arrow_left_line': 'arrow-left-line',
    'arrow_up_line': 'arrow-up-line',
    'arrow_down_line': 'arrow-down-line',
    'undo_arrow': 'arrow-go-back-line',
    'redo_arrow': 'arrow-go-forward-line',
    
    # Content
    'save': 'save-line',
    'save_fill': 'save-fill',
    'save_2': 'save-2-line',
    'save_3': 'save-3-line',
    'file': 'file-line',
    'file_fill': 'file-fill',
    'file_text': 'file-text-line',
    'file_list': 'file-list-line',
    'file_add': 'file-add-line',
    'file_add_fill': 'file-add-fill',
    'folder': 'folder-line',
    'folder_fill': 'folder-fill',
    'folder_open': 'folder-open-line',
    'folder_add': 'folder-add-line',
    'attachment': 'attachment-line',
    'image': 'image-line',
    'table': 'table-line',
    'table_fill': 'table-fill',
    
    # Preferences
    'settings': 'settings-3-line',
    'settings_fill': 'settings-3-fill',
    'palette': 'palette-line',
    'sun': 'sun-line',
    'moon': 'moon-fill',
    'moon_line': 'moon-line',
    'theme': 'contrast-2-line',
    
    # Time & Schedule
    'time': 'time-line',
    'time_fill': 'time-fill',
    'clock': 'timer-line',
    'clock_fill': 'timer-fill',
    'clockwise': 'clockwise-line',
    'calendar': 'calendar-line',
    'calendar_fill': 'calendar-fill',
    'schedule': 'calendar-schedule-line',
    
    # Star & Favorites
    'star': 'star-line',
    'star_fill': 'star-fill',
    'star_s': 'star-s-fill',
    'star_s_line': 'star-s-line',
    'bookmark': 'bookmark-line',
    'bookmark_fill': 'bookmark-fill',
    'heart': 'heart-line',
    'heart_fill': 'heart-fill',
    'thumb_up': 'thumb-up-line',
    'thumb_up_fill': 'thumb-up-fill',
    'like': 'thumb-up-fill',
    
    # Storage & Archive
    'archive': 'archive-line',
    'archive_fill': 'archive-fill',
    'archive_2': 'archive-2-line',
    'archive_2_fill': 'archive-2-fill',
    'box': 'box-3-line',
    'box_fill': 'box-3-fill',
    'hard_drive': 'hard-drive-2-line',
    'cloud': 'cloud-line',
    'cloud_fill': 'cloud-fill',
    'cloud_off': 'cloud-off-line',
    
    # Security
    'shield': 'shield-line',
    'shield_fill': 'shield-fill',
    'key': 'key-line',
    'key_fill': 'key-fill',
    'lock': 'lock-line',
    'lock_fill': 'lock-fill',
    'unlock': 'unlock-line',
    'unlock_fill': 'unlock-fill',
    
    # User & Team
    'user': 'user-line',
    'user_fill': 'user-fill',
    'team': 'team-line',
    'user_add': 'user-add-line',
    'user_settings': 'user-settings-line',
    
    # Transfer & Sync
    'refresh': 'refresh-line',
    'refresh_fill': 'refresh-fill',
    'restart': 'restart-line',
    'swap': 'swap-line',
    'swap_fill': 'swap-fill',
    'exchange': 'exchange-line',
    'exchange_fill': 'exchange-fill',
    'swap_box': 'swap-box-line',
    'swap_box_fill': 'swap-box-fill',
    
    # Help & Docs
    'book': 'book-line',
    'book_fill': 'book-fill',
    'book_open': 'book-open-line',
    'question': 'question-line',
    'question_fill': 'question-fill',
    'lightbulb': 'lightbulb-line',
    'lightbulb_fill': 'lightbulb-fill',
    
    # Tools
    'tools': 'tools-line',
    'hammer': 'hammer-line',
    'bug': 'bug-line',
    'bug_fill': 'bug-fill',
    'buildings': 'buildings-line',
    'cpu': 'cpu-line',
    'command': 'command-line',
    
    # Charts
    'bar_chart': 'bar-chart-2-line',
    'pie_chart': 'pie-chart-2-line',
    'line_chart': 'line-chart-line',
    
    # Network
    'wifi': 'wifi-line',
    'wifi_off': 'wifi-off-line',
    'global': 'global-line',
    'computer': 'computer-line',
    'earth': 'earth-line',
    
    # Misc
    'stop': 'stop-line',
    'stop_fill': 'stop-fill',
    'pushpin': 'pushpin-line',
    'pushpin_fill': 'pushpin-fill',
    'share': 'share-forward-line',
    'share_fill': 'share-forward-fill',
    'printer': 'printer-line',
    'external_link': 'external-link-line',
    'flag': 'flag-line',
    'flag_fill': 'flag-fill',
    'speed': 'speed-line',
    'speed_fill': 'speed-fill',
    'emotion': 'emotion-line',
    'emotion_fill': 'emotion-fill',
    'gift': 'gift-line',
    'trophy': 'trophy-line',
    'medal': 'medal-line',
    'fire': 'fire-line',
    
    # Text formatting
    'bold': 'bold',
    'italic': 'italic',
    'underline': 'underline',
    'strikethrough': 'strikethrough',
    'text': 'text',
    
    # Git
    'git_branch': 'git-branch-line',
    'git_commit': 'git-commit-line',
    'git_repo': 'git-repository-line',
    'git_pull': 'git-pull-request-line',
    
    # Window
    'window': 'window-2-line',
    'window_fill': 'window-2-fill',
    'dashboard': 'dashboard-3-line',
    
    # Misc UI
    'cursor': 'cursor-line',
    'mail': 'mail-line',
    'mail_fill': 'mail-fill',
    'phone': 'phone-line',
    'translate': 'translate-2',
    'scissors': 'scissors-line',
    'scissors_fill': 'scissors-fill',
}

print("# Generated by parse_css.py - Remix Icon v4.9.0 Unicode Mapping")
print("# Total available icons: 3227")
print()
print("ICON_MAP = {")

not_found = []
for key, css_name in needed.items():
    if css_name in icons:
        code = icons[css_name]
        print(f"    '{key}': '\\u{code}',  # ri-{css_name}")
    else:
        not_found.append((key, css_name))

print("}")

if not_found:
    print(f"\n# NOT FOUND ({len(not_found)}):")
    for key, css_name in not_found:
        # Try fuzzy match
        parts = css_name.split('-')
        base = parts[0]
        matches = [k for k in icons if k.startswith(base) and k.endswith(parts[-1] if len(parts) > 1 else '')]
        alt = [k for k in icons if k == css_name]
        all_similar = [k for k in icons if css_name.replace('-', '') in k.replace('-', '')]
        if all_similar:
            print(f"#   '{key}': ???  # ri-{css_name} -> try: {all_similar[:3]}")
        else:
            print(f"#   '{key}': ???  # ri-{css_name} -> no match")
