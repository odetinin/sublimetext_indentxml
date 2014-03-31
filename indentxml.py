import sublime
import sublime_plugin
import re
import json
import os.path
from xml.dom.minidom import *

class BaseIndentCommand(sublime_plugin.TextCommand):
    def __init__(self, view):
        self.view = view
        self.language = self.get_language()
        self.filename = view.file_name()

    def get_language(self):
        syntax = self.view.settings().get('syntax')
        language = os.path.basename(syntax).replace('.tmLanguage', '').lower() if syntax != None else "plain text"
        return language

    def check_enabled(self, lang):
        return True

    def is_enabled(self):
        """
        Enables or disables the 'indent' command.
        Command will be disabled if there are currently no text selections and current file is not 'XML' or 'Plain Text'.
        This helps clarify to the user about when the command can be executed, especially useful for UI controls.
        """
        if self.view == None:
            return False

        return self.check_enabled(self.get_language())

    def run(self, edit):
        """
        Main plugin logic for the 'indent' command.
        """

        if self.filename == None:
            return False

        extensions = [
            '.sublime-build',
            '.sublime-commands',
            '.sublime-completions',
            '.sublime-keymap',
            '.sublime-menu',
            '.sublime-mousemap',
            '.sublime-project',
            '.sublime-settings',
            '.sublime-workspace',
        ]

        if os.path.splitext(self.filename)[1] in extensions:
            return

        view = self.view
        regions = view.sel()
        # if there are more than 1 region or region one and it's not empty
        if len(regions) > 1 or not regions[0].empty():
                for region in view.sel():
                    if not region.empty():
                        s = view.substr(region).strip()
                        s = self.indent(s)
                        view.replace(edit, region, s)
        else:   #format all text
                alltextreg = sublime.Region(0, view.size())
                s = view.substr(alltextreg).strip()
                s = self.indent(s)
                view.replace(edit, alltextreg, s)


class AutoIndentCommand(BaseIndentCommand):
    def get_text_type(self, s):
        language =  self.language
        if language == 'xml':
            return 'xml'
        if language == 'json':
            return 'json'
        if language == 'plain text' and s:
            if s[0] == '<':
                return 'xml'
            if s[0] == '{' or s[0] == '[':
                return 'json'

        return 'notsupported'

    def indent(self, s):
        text_type = self.get_text_type(s)
        if text_type == 'xml':
            command = IndentXmlCommand(self.view)
        if text_type == 'json':
            command = IndentJsonCommand(self.view)
        if text_type == 'notsupported':
            return s

        return command.indent(s)

    def check_enabled(self, lang):
        return True


class IndentXmlCommand(BaseIndentCommand):
    def indent(self, s):
        # convert to utf
        s = s.encode("utf-8")
        xmlheader = re.compile(b"<\?.*\?>").match(s)
        # convert to plain string without indents and spaces
        s = re.compile(b'>\s+([^\s])', re.DOTALL).sub(b'>\g<1>', s)
        # replace tags to convince minidom process cdata as text
        s = s.replace(b'<![CDATA[', b'%CDATAESTART%').replace(b']]>', b'%CDATAEEND%')
        try:
            s = parseString(s).toprettyxml()
        except Exception as e:
            sublime.active_window().run_command("show_panel", {"panel": "console", "toggle": True})
            raise e
        # remove line breaks
        s = re.compile('>\n\s+([^<>\s].*?)\n\s+</', re.DOTALL).sub('>\g<1></', s)
        # restore cdata
        s = s.replace('%CDATAESTART%', '<![CDATA[').replace('%CDATAEEND%', ']]>')
        # remove xml header
        s = s.replace("<?xml version=\"1.0\" ?>", "").strip()
        if xmlheader:
                s = xmlheader.group().decode("utf-8") + "\n" + s
        return s

    def check_enabled(self, language):
        return ((language == "xml") or (language == "plain text"))


class IndentJsonCommand(BaseIndentCommand):

    line_comment_re = re.compile(r'[ \t]*//.*')
    block_comment_re = re.compile(r'/\*(.*?)\*/', re.DOTALL)
    inner_re = re.compile(r'^([^\r\n]*?(\r?\n|$))', re.MULTILINE)

    @classmethod
    def strip_comment(cls, match):
        """Return a block comment stripped of all content on each line, but leaving the EOL."""
        inner = cls.inner_re.sub(r'\2', match.group(1))
        return inner

    def check_enabled(self, language):
        return ((language == "json") or (language == "plain text"))

    def indent(self, s):

        s = self.line_comment_re.sub('', s)
        s = self.block_comment_re.sub(self.strip_comment, s)
        parsed = json.loads(s)

        return json.dumps(parsed, sort_keys=True, indent=4, separators=(',', ': '))