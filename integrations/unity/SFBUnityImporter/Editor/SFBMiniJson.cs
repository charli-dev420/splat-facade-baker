#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text;

namespace SFB.Editor
{
    internal static class SFBMiniJson
    {
        public static object Parse(string json)
        {
            if (string.IsNullOrWhiteSpace(json))
            {
                throw new FormatException("JSON is empty.");
            }
            var parser = new Parser(json);
            return parser.ParseValue();
        }

        public static Dictionary<string, object> ParseObject(string json)
        {
            var value = Parse(json);
            if (value is Dictionary<string, object> dict)
            {
                return dict;
            }
            throw new FormatException("JSON root is not an object.");
        }

        private sealed class Parser
        {
            private readonly string _json;
            private int _index;

            public Parser(string json)
            {
                _json = json;
            }

            public object ParseValue()
            {
                SkipWhitespace();
                if (_index >= _json.Length)
                {
                    throw Error("Unexpected end of JSON.");
                }

                char c = _json[_index];
                if (c == '{') return ParseObjectInternal();
                if (c == '[') return ParseArrayInternal();
                if (c == '"') return ParseStringInternal();
                if (c == '-' || char.IsDigit(c)) return ParseNumberInternal();
                if (Match("true")) return true;
                if (Match("false")) return false;
                if (Match("null")) return null;
                throw Error($"Unexpected character '{c}'.");
            }

            private Dictionary<string, object> ParseObjectInternal()
            {
                Expect('{');
                var obj = new Dictionary<string, object>();
                SkipWhitespace();
                if (TryConsume('}')) return obj;

                while (true)
                {
                    SkipWhitespace();
                    string key = ParseStringInternal();
                    SkipWhitespace();
                    Expect(':');
                    object value = ParseValue();
                    obj[key] = value;
                    SkipWhitespace();
                    if (TryConsume('}')) break;
                    Expect(',');
                }
                return obj;
            }

            private List<object> ParseArrayInternal()
            {
                Expect('[');
                var arr = new List<object>();
                SkipWhitespace();
                if (TryConsume(']')) return arr;

                while (true)
                {
                    arr.Add(ParseValue());
                    SkipWhitespace();
                    if (TryConsume(']')) break;
                    Expect(',');
                }
                return arr;
            }

            private string ParseStringInternal()
            {
                Expect('"');
                var sb = new StringBuilder();
                while (_index < _json.Length)
                {
                    char c = _json[_index++];
                    if (c == '"') return sb.ToString();
                    if (c != '\\')
                    {
                        sb.Append(c);
                        continue;
                    }

                    if (_index >= _json.Length) throw Error("Invalid escape sequence.");
                    char esc = _json[_index++];
                    switch (esc)
                    {
                        case '"': sb.Append('"'); break;
                        case '\\': sb.Append('\\'); break;
                        case '/': sb.Append('/'); break;
                        case 'b': sb.Append('\b'); break;
                        case 'f': sb.Append('\f'); break;
                        case 'n': sb.Append('\n'); break;
                        case 'r': sb.Append('\r'); break;
                        case 't': sb.Append('\t'); break;
                        case 'u':
                            if (_index + 4 > _json.Length) throw Error("Invalid unicode escape.");
                            string hex = _json.Substring(_index, 4);
                            sb.Append((char)int.Parse(hex, NumberStyles.HexNumber, CultureInfo.InvariantCulture));
                            _index += 4;
                            break;
                        default:
                            throw Error($"Invalid escape character '{esc}'.");
                    }
                }
                throw Error("Unterminated string.");
            }

            private double ParseNumberInternal()
            {
                int start = _index;
                if (_json[_index] == '-') _index++;
                while (_index < _json.Length && char.IsDigit(_json[_index])) _index++;
                if (_index < _json.Length && _json[_index] == '.')
                {
                    _index++;
                    while (_index < _json.Length && char.IsDigit(_json[_index])) _index++;
                }
                if (_index < _json.Length && (_json[_index] == 'e' || _json[_index] == 'E'))
                {
                    _index++;
                    if (_index < _json.Length && (_json[_index] == '+' || _json[_index] == '-')) _index++;
                    while (_index < _json.Length && char.IsDigit(_json[_index])) _index++;
                }
                string number = _json.Substring(start, _index - start);
                return double.Parse(number, CultureInfo.InvariantCulture);
            }

            private bool Match(string literal)
            {
                SkipWhitespace();
                if (_index + literal.Length > _json.Length) return false;
                if (string.CompareOrdinal(_json, _index, literal, 0, literal.Length) != 0) return false;
                _index += literal.Length;
                return true;
            }

            private void SkipWhitespace()
            {
                while (_index < _json.Length && char.IsWhiteSpace(_json[_index])) _index++;
            }

            private void Expect(char c)
            {
                SkipWhitespace();
                if (_index >= _json.Length || _json[_index] != c)
                {
                    throw Error($"Expected '{c}'.");
                }
                _index++;
            }

            private bool TryConsume(char c)
            {
                SkipWhitespace();
                if (_index < _json.Length && _json[_index] == c)
                {
                    _index++;
                    return true;
                }
                return false;
            }

            private FormatException Error(string message)
            {
                return new FormatException($"{message} At index {_index}.");
            }
        }
    }
}
#endif
