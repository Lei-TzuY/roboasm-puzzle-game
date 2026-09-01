(() => {
  'use strict';

  // Browser-side compiler compatibility layer. Python remains authoritative;
  // this module mirrors its preprocessing/assembly pipeline closely enough for
  // deterministic cross-runtime regression testing and interactive execution.
  if (typeof lex !== 'function' || typeof assemble !== 'function') {
    throw new Error('RoboASM Web preprocessor could not find lex/assemble');
  }
  if (assemble.__roboasmPreprocessorWrapped) return;

  const originalFoldConstants = typeof foldConstants === 'function'
    ? foldConstants
    : null;
  const DATA_MEMORY_KEY = '__roboasmDataMemory';
  const INCLUDE_DIRECTIVES = new Set(['#include', '@include', 'include']);
  const DEFINE_DIRECTIVES = new Set(['#define', '@define']);
  const DATA_DIRECTIVES = new Set(['db', '.db', 'dw', '.dw', 'array', '.array']);
  const MACRO_START = new Set(['%macro', '#macro', 'macro']);
  const MACRO_END = new Set(['%endmacro', '#endmacro', 'endmacro']);

  function own(mapping, key) {
    return Object.prototype.hasOwnProperty.call(mapping, key);
  }

  function partsOf(token) {
    return token && Array.isArray(token.parts) ? token.parts : [];
  }

  function cloneToken(token, parts = partsOf(token)) {
    return {
      line_num: token ? token.line_num : undefined,
      raw_line: token ? token.raw_line : undefined,
      parts: [...parts],
    };
  }

  function parseScalar(raw, context = 'value') {
    const text = String(raw);
    if (/^[+-]?\d+$/.test(text)) {
      const value = Number(text);
      if (!Number.isSafeInteger(value)) {
        throw new Error(`${context} '${text}' exceeds the Web VM safe-integer range`);
      }
      return value;
    }
    return raw;
  }

  function includeSourceMap() {
    const mapping = globalThis.ROBOASM_WEB_INCLUDE_SOURCES;
    return mapping && typeof mapping === 'object' ? mapping : {};
  }

  function normalizeIncludeTarget(raw) {
    return String(raw || '')
      .replace(/^['"]|['"]$/g, '')
      .replaceAll('\\', '/');
  }

  function expandIncludes(tokens, depth = 0) {
    if (depth > 10) throw new Error('Max include recursion depth exceeded');
    const expanded = [];
    const sources = includeSourceMap();

    for (const token of tokens) {
      const parts = partsOf(token);
      if (parts.length === 0) continue;
      const first = String(parts[0]).toLowerCase();
      if (!INCLUDE_DIRECTIVES.has(first)) {
        expanded.push(cloneToken(token));
        continue;
      }

      if (parts.length < 2) throw new Error('Missing include target file');
      const target = normalizeIncludeTarget(parts[1]);
      if (!own(sources, target)) {
        throw new Error(`Include file '${target}' not found in Web include map`);
      }
      const nestedTokens = lex(String(sources[target]));
      expanded.push(...expandIncludes(nestedTokens, depth + 1));
    }
    return expanded;
  }

  function processConstantsAndData(tokens) {
    const constants = {};
    const dataMemory = {};
    const filtered = [];
    let dataAddress = 0;

    for (const token of tokens) {
      const parts = partsOf(token);
      if (parts.length === 0) continue;
      const first = String(parts[0]).toLowerCase();

      if (DEFINE_DIRECTIVES.has(first)) {
        if (parts.length >= 3) {
          constants[parts[1]] = parseScalar(parts[2], 'Constant');
        }
        continue;
      }

      if (parts.length >= 3 && ['equ', '.equ'].includes(String(parts[1]).toLowerCase())) {
        constants[parts[0]] = parseScalar(parts[2], 'Constant');
        continue;
      }

      if (DATA_DIRECTIVES.has(first)) {
        for (const raw of parts.slice(1)) {
          dataMemory[dataAddress] = parseScalar(raw, 'Data value');
          dataAddress += 1;
        }
        continue;
      }

      filtered.push(cloneToken(token));
    }

    return {tokens: filtered, constants, dataMemory};
  }

  function processConditionals(tokens, constants) {
    const result = [];
    const stack = [true];

    for (const token of tokens) {
      const parts = partsOf(token);
      if (parts.length === 0) continue;
      const first = String(parts[0]).toLowerCase();

      if (first === '#ifdef' || first === '@ifdef') {
        const symbol = parts.length > 1 ? parts[1] : '';
        stack.push(stack[stack.length - 1] && own(constants, symbol));
        continue;
      }
      if (first === '#ifndef' || first === '@ifndef') {
        const symbol = parts.length > 1 ? parts[1] : '';
        stack.push(stack[stack.length - 1] && !own(constants, symbol));
        continue;
      }
      if (first === '#else' || first === '@else') {
        if (stack.length <= 1) throw new Error('Unexpected #else directive');
        stack[stack.length - 1] = stack[stack.length - 2] && !stack[stack.length - 1];
        continue;
      }
      if (first === '#endif' || first === '@endif') {
        if (stack.length <= 1) throw new Error('Unexpected #endif directive');
        stack.pop();
        continue;
      }

      if (stack[stack.length - 1]) result.push(cloneToken(token));
    }

    if (stack.length > 1) {
      throw new Error('Unterminated #ifdef/#ifndef directive block');
    }
    return result;
  }

  function expandMacros(tokens) {
    const macroDefs = {};
    const filtered = [];
    let inMacro = null;

    for (const token of tokens) {
      const parts = partsOf(token);
      if (parts.length === 0) continue;
      const first = String(parts[0]).toLowerCase();

      if (MACRO_START.has(first)) {
        if (parts.length < 2) throw new Error('Macro definition requires a name');
        inMacro = {name: parts[1], args: parts.slice(2), body: []};
        continue;
      }

      if (MACRO_END.has(first)) {
        if (!inMacro) throw new Error('Unexpected %endmacro directive');
        macroDefs[inMacro.name] = inMacro;
        inMacro = null;
        continue;
      }

      if (inMacro) {
        inMacro.body.push(cloneToken(token));
        continue;
      }

      if (own(macroDefs, parts[0])) {
        const macro = macroDefs[parts[0]];
        const invocationArgs = parts.slice(1);
        const argMap = {};
        macro.args.forEach((arg, index) => {
          if (index < invocationArgs.length) argMap[arg] = invocationArgs[index];
        });
        for (const bodyToken of macro.body) {
          filtered.push(cloneToken(
            token,
            partsOf(bodyToken).map(part => own(argMap, part) ? argMap[part] : part),
          ));
        }
      } else {
        filtered.push(cloneToken(token));
      }
    }

    if (inMacro) throw new Error(`Unclosed macro definition for '${inMacro.name}'`);
    return filtered;
  }

  function resolveArgument(raw, constants, labels) {
    if (own(constants, raw)) return constants[raw];
    if (own(labels, raw)) return labels[raw];
    return parseScalar(raw, 'Integer operand') instanceof Number
      ? parseScalar(raw, 'Integer operand')
      : (/^[+-]?\d+$/.test(String(raw))
          ? parseScalar(raw, 'Integer operand')
          : String(raw).toUpperCase());
  }

  function assembleProcessed(tokens, constants, optimize) {
    const labels = {};
    const filtered = [];
    let instructionIndex = 0;

    for (const token of tokens) {
      const parts = partsOf(token);
      if (parts.length === 0) continue;
      const first = parts[0];
      if (String(first).endsWith(':')) {
        const label = String(first).slice(0, -1);
        labels[label] = instructionIndex;
        if (parts.length > 1) {
          filtered.push(cloneToken(token, parts.slice(1)));
          instructionIndex += 1;
        }
      } else {
        filtered.push(cloneToken(token));
        instructionIndex += 1;
      }
    }

    let instructions = filtered.map(token => {
      const parts = partsOf(token);
      const opcode = String(parts[0]).toUpperCase();
      const args = parts.slice(1).map(arg => {
        if (own(constants, arg)) return constants[arg];
        if (own(labels, arg)) return labels[arg];
        const text = String(arg);
        if (/^[+-]?\d+$/.test(text)) return parseScalar(text, 'Integer operand');
        return text.toUpperCase();
      });
      return {opcode, args, line_num: token.line_num};
    });

    if (optimize && originalFoldConstants) {
      instructions = originalFoldConstants(instructions);
    }
    return instructions;
  }

  function compatibleAssemble(tokens, optimize = false) {
    const expanded = expandIncludes(tokens);
    const processed = processConstantsAndData(expanded);
    const conditional = processConditionals(processed.tokens, processed.constants);
    const macroExpanded = expandMacros(conditional);
    const instructions = assembleProcessed(
      macroExpanded,
      processed.constants,
      optimize,
    );

    Object.defineProperty(instructions, DATA_MEMORY_KEY, {
      value: processed.dataMemory,
      enumerable: false,
      configurable: false,
      writable: false,
    });
    return instructions;
  }

  compatibleAssemble.__roboasmPreprocessorWrapped = true;
  assemble = compatibleAssemble;

  globalThis.ROBOASM_WEB_PREPROCESSOR = Object.freeze({
    version: 1,
    features: [
      'project-includes',
      'define',
      'equ',
      'conditional-compilation',
      'macros',
      'data-directives',
      'labels',
      'constant-resolution',
    ],
  });
})();
