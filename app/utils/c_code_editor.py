from PyQt5.Qsci import QsciScintilla, QsciLexerCPP, QsciAPIs
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtCore import Qt

class CCodeEditor(QsciScintilla):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_editor()
        self._init_lexer()
        self._init_apis()
        self._init_margins()
        self._init_auto_completion()
        self._init_indentation()
        self._init_brace_matching()
        self._init_other_settings()

    def _init_editor(self):
        """初始化编辑器基本设置"""
        # 设置字体
        font = QFont()
        font.setFamily('Consolas')
        font.setFixedPitch(True)
        font.setPointSize(11)
        self.setFont(font)
        
        # 设置自动缩进
        self.setAutoIndent(True)
        self.setIndentationGuides(True)
        self.setIndentationsUseTabs(False)
        self.setTabWidth(4)
        
        # 设置边距
        self.setMarginWidth(0, 0)  # 隐藏第一个边距
        self.setMarginWidth(1, "0000")  # 行号边距
        self.setMarginWidth(2, 0)  # 隐藏第二个边距
        
        # 设置边距颜色
        self.setMarginsForegroundColor(QColor("#CCCCCC"))
        self.setMarginsBackgroundColor(QColor("#2B2B2B"))
        
        # 设置选中行的背景色
        self.setCaretLineVisible(True)
        #self.setCaretLineBackgroundColor(QColor("#3E3E3E"))
        
        # 设置括号匹配
        self.setBraceMatching(QsciScintilla.SloppyBraceMatch)
        
        # 设置代码折叠
        self.setFolding(QsciScintilla.BoxedTreeFoldStyle)
        
        # 设置自动换行
        self.setWrapMode(QsciScintilla.WrapWord)

    def _init_lexer(self):
        """初始化语法高亮器"""
        self.lexer = QsciLexerCPP()
        self.lexer.setFont(self.font())
        
        # 设置颜色主题
        self.lexer.setColor(QColor("#97de78"), QsciLexerCPP.Comment)  # 注释
        self.lexer.setColor(QColor("#97de78"), QsciLexerCPP.CommentLine)  # 行注释
        self.lexer.setColor(QColor("#CE9178"), QsciLexerCPP.RawString)  # 字符串
        self.lexer.setColor(QColor("#ffa500"), QsciLexerCPP.Keyword)  # 关键字
        self.lexer.setColor(QColor("#B5CEA8"), QsciLexerCPP.Number)  # 数字
        self.lexer.setColor(QColor("#000000"), QsciLexerCPP.Identifier)  # 标识符
        
        self.setLexer(self.lexer)

    def _init_apis(self):
        """初始化自动补全API"""
        self.apis = QsciAPIs(self.lexer)
        
        # 添加C语言关键字
        c_keywords = [
            "auto", "break", "case", "char", "const", "continue", "default", "do",
            "double", "else", "enum", "extern", "float", "for", "goto", "if",
            "int", "long", "register", "return", "short", "signed", "sizeof", "static",
            "struct", "switch", "typedef", "union", "unsigned", "void", "volatile", "while"
        ]
        
        '''
        c_functions = [
            "printf", "scanf", "malloc", "free", "strlen", "strcpy", "strcat",
            "memcpy", "memset", "fopen", "fclose", "fread", "fwrite"
        ]
        '''

        
        # 添加所有关键字和函数到API
        for keyword in c_keywords:
            self.apis.add(keyword)
        
        self.apis.prepare()

    def _init_margins(self):
        """初始化边距设置"""
        # 显示行号
        self.setMarginLineNumbers(1, True)
        self.setMarginWidth(1, "0000")
        
        # 设置代码折叠边距
        self.setMarginWidth(2, 16)
        self.setMarginSensitivity(2, True)
        self.setFolding(QsciScintilla.BoxedTreeFoldStyle)

    def _init_auto_completion(self):
        """初始化自动补全设置"""
        self.setAutoCompletionSource(QsciScintilla.AcsAll)  # 使用所有可用的自动补全源
        self.setAutoCompletionThreshold(2)  # 输入2个字符后显示自动补全
        self.setAutoCompletionCaseSensitivity(False)  # 不区分大小写
        self.setAutoCompletionReplaceWord(False)  # 不替换整个词
        self.setAutoCompletionShowSingle(True)  # 只有一个选项时也显示

    def _init_indentation(self):
        """初始化缩进设置"""
        self.setAutoIndent(True)  # 启用自动缩进
        self.setIndentationGuides(True)  # 显示缩进指南
        self.setIndentationsUseTabs(False)  # 使用空格而不是制表符
        self.setTabWidth(4)  # 设置制表符宽度为4个空格
        self.setTabIndents(True)  # 启用制表符缩进
        self.setBackspaceUnindents(True)  # 启用退格键取消缩进

    def _init_brace_matching(self):
        """初始化括号匹配设置"""
        self.setBraceMatching(QsciScintilla.SloppyBraceMatch)  # 设置括号匹配模式
        self.setMatchedBraceBackgroundColor(QColor("#5eb8e8"))  # 设置匹配括号的背景色
        self.setUnmatchedBraceBackgroundColor(QColor("#5eb8e8"))  # 设置不匹配括号的背景色

    def _init_other_settings(self):
        """初始化其他设置"""
        # 设置光标
        self.setCaretWidth(2)  # 设置光标宽度
        self.setCaretForegroundColor(QColor("#000000"))  # 设置光标颜色
        
        # 设置选中文本的颜色
        self.setSelectionBackgroundColor(QColor("#3A7DD4"))
        self.setSelectionForegroundColor(QColor("#FFFFFF"))

        # 设置背景色和前景色
        self.setPaper(QColor("#2B2B2B"))  # 设置背景色
        self.setColor(QColor("#D4D4D4"))  # 设置前景色
        
        # 设置行间距
        self.setMarginLineNumbers(1, True)
        self.setMarginWidth(1, "0000")
        
        # 启用代码折叠
        self.setFolding(QsciScintilla.BoxedTreeFoldStyle)
        
        # 设置自动换行
        self.setWrapMode(QsciScintilla.WrapWord)

    def set_text(self, text: str):
        """设置编辑器文本"""
        self.setText(text)

    def get_text(self) -> str:
        """获取编辑器文本"""
        return self.text()

    def clear_text(self):
        """清空编辑器文本"""
        self.clear()