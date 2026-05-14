"""
sql_editor_helper.py
SQL 编辑器智能提示和自动补全 helper
"""
from PySide6.QtCore import QStringListModel, Qt
from PySide6.QtWidgets import QCompleter
from PySide6.QtGui import QTextCharFormat, QColor, QFont


SQL_KEYWORDS = [
    "SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP",
    "FROM", "WHERE", "INTO", "VALUES", "SET", "JOIN", "INNER JOIN",
    "LEFT JOIN", "RIGHT JOIN", "ON", "GROUP BY", "ORDER BY", "HAVING",
    "LIMIT", "OFFSET", "DISTINCT", "AS", "AND", "OR", "NOT", "IN",
    "EXISTS", "BETWEEN", "LIKE", "IS NULL", "IS NOT NULL", "CASE",
    "WHEN", "THEN", "ELSE", "END", "COUNT", "SUM", "AVG", "MIN", "MAX",
    "COALESCE", "CAST", "CONVERT", "UPPER", "LOWER", "TRIM", "SUBSTRING",
    "LENGTH", "DATE", "TIME", "TIMESTAMP", "NOW", "CURRENT_DATE",
    "PRIMARY KEY", "FOREIGN KEY", "UNIQUE", "CHECK", "DEFAULT",
    "INT", "VARCHAR", "TEXT", "DECIMAL", "DATETIME", "BOOLEAN",
    "BEGIN", "COMMIT", "ROLLBACK", "USE", "SHOW", "DESCRIBE", "EXPLAIN",
    "UNION", "INTERSECT", "EXCEPT", "ASC", "DESC", "NULL", "TRUE", "FALSE",
]


class SqlHighlighter:
    """SQL 语法高亮器"""
    
    def __init__(self, document, tokens=None):
        from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat
        from PySide6.QtCore import QRegularExpression
        
        self.highlighter = QSyntaxHighlighter(document)
        self.tokens = tokens or {}
        
        self.keyword_format = QTextCharFormat()
        self.keyword_format.setForeground(QColor(self.tokens.get('accent', '#1677ff')))
        self.keyword_format.setFontWeight(QFont.Weight.Bold)
        
        self.string_format = QTextCharFormat()
        self.string_format.setForeground(QColor(self.tokens.get('success', '#16a34a')))
        
        self.number_format = QTextCharFormat()
        self.number_format.setForeground(QColor(self.tokens.get('warning', '#d97706')))
        
        self.comment_format = QTextCharFormat()
        self.comment_format.setForeground(QColor(self.tokens.get('text_muted', '#94a3b8')))
        self.comment_format.setFontItalic(True)
        
        self.rules = []
        
        for keyword in SQL_KEYWORDS:
            pattern = QRegularExpression(f'\\b{keyword}\\b', QRegularExpression.PatternOption.CaseInsensitiveOption)
            self.rules.append((pattern, self.keyword_format))
        
        self.rules.append((QRegularExpression(r"'[^']*'"), self.string_format))
        self.rules.append((QRegularExpression(r'"[^"]*"'), self.string_format))
        self.rules.append((QRegularExpression(r'\b\d+(\.\d+)?\b'), self.number_format))
        self.rules.append((QRegularExpression(r'--[^\n]*'), self.comment_format))
        
        self.highlighter.highlightBlock = self.highlight_block
    
    def highlight_block(self, text):
        for pattern, format in self.rules:
            match_iterator = pattern.globalMatch(text)
            while match_iterator.hasNext():
                match = match_iterator.next()
                self.highlighter.setFormat(match.capturedStart(), match.capturedLength(), format)


class SqlCompleter:
    """SQL 自动补全器"""
    
    def __init__(self, text_edit, connector=None):
        self.text_edit = text_edit
        self.connector = connector
        self.completer = QCompleter()
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.completer.setMaxVisibleItems(10)
        
        self.update_completer_keywords()
        self.text_edit.textChanged.connect(self.on_text_changed)
        self.completer.activated.connect(self.insert_completion)
    
    def update_completer_keywords(self):
        model = QStringListModel(SQL_KEYWORDS)
        self.completer.setModel(model)
        self.completer.setCompletionPrefix("")
    
    def update_table_names(self, table_names):
        if not table_names:
            return
        all_items = SQL_KEYWORDS + [f"[{t}]" for t in table_names]
        model = QStringListModel(all_items)
        self.completer.setModel(model)
    
    def update_column_names(self, column_names):
        if not column_names:
            return
        all_items = SQL_KEYWORDS + [f"[{c}]" for c in column_names]
        model = QStringListModel(all_items)
        self.completer.setModel(model)
    
    def on_text_changed(self):
        cursor = self.text_edit.textCursor()
        text = cursor.block().text()[:cursor.positionInBlock()]
        
        word_start = len(text) - 1
        while word_start >= 0 and (text[word_start].isalnum() or text[word_start] == '_'):
            word_start -= 1
        word_start += 1
        
        current_word = text[word_start:]
        
        if len(current_word) >= 1:
            self.completer.setCompletionPrefix(current_word)
            
            popup = self.completer.popup()
            if popup.isVisible():
                return
            
            cr = self.text_edit.cursorRect()
            cr.setWidth(
                self.completer.popup().sizeHintForColumn(0) + 
                self.completer.popup().verticalScrollBar().sizeHint().width()
            )
            self.completer.complete(cr)
    
    def insert_completion(self, completion):
        if self.completer.widget() != self.text_edit:
            return
        
        cursor = self.text_edit.textCursor()
        extra = len(completion) - len(self.completer.completionPrefix())
        cursor.movePosition(cursor.MoveOperation.Left)
        cursor.movePosition(cursor.MoveOperation.EndOfWord)
        cursor.insertText(completion[-extra:] if extra > 0 else completion)
        self.text_edit.setTextCursor(cursor)


def apply_sql_highlighter(text_edit, tokens=None):
    document = text_edit.document()
    highlighter = SqlHighlighter(document, tokens)
    return highlighter


def setup_sql_completer(text_edit, connector=None):
    completer = SqlCompleter(text_edit, connector)
    return completer