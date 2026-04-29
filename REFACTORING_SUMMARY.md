# 项目重构总结 - 原始DSL保存机制

## 重构目标

将项目架构从"UI → DSL转换 → 验证"改为"保存原始DSL → 直接使用DSL → 验证"，避免UI和模型之间的重复转换，提高可靠性和性能。

## 主要变更

### 1. 模型层 (`app/model/model.py`)

**StateManager 类新增属性：**
```python
class StateManager:
    def __init__(self, root_state: Optional[State] = None):
        # ... 原有属性 ...
        self.original_dsl_code: Optional[str] = None  # 保存原始DSL代码
        self.source_file_path: Optional[str] = None   # 保存源文件路径
```

**作用：**
- `original_dsl_code`: 存储从文件导入时的原始DSL代码
- `source_file_path`: 存储源文件路径，便于追踪和调试

### 2. DSL转换工具 (`app/utils/dsl_to_ui.py`)

**`dsl_to_state_manager` 函数修改：**
```python
def dsl_to_state_manager(file_path: str) -> StateManager:
    # 读取原始DSL代码
    with open(file_path, 'r', encoding='utf-8') as f:
        original_dsl_code = f.read()
    
    # 解析并转换
    state_machine, variable_definitions, forced = parse_fcstm_file(file_path)
    state_manager = convert_state_machine_to_state_manager(state_machine, variable_definitions)
    
    # 保存原始DSL代码和文件路径
    state_manager.original_dsl_code = original_dsl_code
    state_manager.source_file_path = file_path
    
    return state_manager
```

**作用：**
- 在导入模型时自动保存原始DSL代码
- 保存文件路径以便后续引用

### 3. 可达性验证 (`app/widget/dialog_reachability_val.py`)

**修改前：**
```python
def _on_accept(self):
    # 将UI中的StateManager转换为FCSTM格式
    dsl_code = state_manager_to_dsl(self.state_manager)
    ast_node = parse_with_grammar_entry(dsl_code, entry_name='state_machine_dsl')
    model = parse_dsl_node_to_state_machine(ast_node)
```

**修改后：**
```python
def _on_accept(self):
    # 优先使用原始DSL代码，如果没有则从UI转换
    if self.state_manager.original_dsl_code:
        dsl_code = self.state_manager.original_dsl_code
    else:
        dsl_code = state_manager_to_dsl(self.state_manager)
    
    ast_node = parse_with_grammar_entry(dsl_code, entry_name='state_machine_dsl')
    model = parse_dsl_node_to_state_machine(ast_node)
```

### 4. 模型仿真 (`app/widget/dialog_simulate.py`)

**修改前：**
```python
def _init_model(self):
    # 将UI中的StateManager转换为FCSTM格式
    dsl_code = state_manager_to_dsl(self.state_manager)
    ast_node = parse_with_grammar_entry(dsl_code, entry_name='state_machine_dsl')
    self.model = parse_dsl_node_to_state_machine(ast_node)
```

**修改后：**
```python
def _init_model(self):
    # 优先使用原始DSL代码，如果没有则从UI转换
    if self.state_manager.original_dsl_code:
        dsl_code = self.state_manager.original_dsl_code
    else:
        dsl_code = state_manager_to_dsl(self.state_manager)
    
    ast_node = parse_with_grammar_entry(dsl_code, entry_name='state_machine_dsl')
    self.model = parse_dsl_node_to_state_machine(ast_node)
```

### 5. 互斥性验证 (`app/widget/dialog_exclusive_val.py`)

**添加当前模型时的修改：**
```python
def _on_add_current_model(self):
    # 优先使用原始DSL代码，如果没有则从UI转换
    if self.state_manager.original_dsl_code:
        dsl_code = self.state_manager.original_dsl_code
    else:
        dsl_code = state_manager_to_dsl(self.state_manager)
    
    ast_node = parse_with_grammar_entry(dsl_code, entry_name='state_machine_dsl')
    model = parse_dsl_node_to_state_machine(ast_node)
```

## 优势

### 1. **避免信息丢失**
- 原始DSL可能包含UI无法完全表示的信息（如注释、特殊格式等）
- 直接使用原始DSL确保验证时使用的是完整的模型信息

### 2. **提高性能**
- 减少了UI → DSL的转换步骤
- 特别是在多次验证时，避免重复转换

### 3. **提高可靠性**
- 减少转换环节，降低出错概率
- 验证结果更准确，因为使用的是原始模型

### 4. **向后兼容**
- 保留了从UI转换的fallback机制
- 对于手动创建的模型（没有导入文件），仍然可以正常工作

### 5. **便于调试**
- 保存了源文件路径，便于追踪问题
- 可以直接查看原始DSL代码

## 使用场景

### 场景1：从文件导入模型
```python
# 用户导入 example.fcstm
state_manager = dsl_to_state_manager("example.fcstm")
# state_manager.original_dsl_code 包含原始DSL
# state_manager.source_file_path = "example.fcstm"

# 进行可达性验证时
# 直接使用 state_manager.original_dsl_code，无需转换
```

### 场景2：手动创建模型
```python
# 用户在UI中手动创建状态机
state_manager = StateManager()
# state_manager.original_dsl_code = None

# 进行可达性验证时
# 自动fallback到 state_manager_to_dsl(state_manager)
```

### 场景3：导入后修改
```python
# 用户导入模型后在UI中进行了修改
# state_manager.original_dsl_code 仍然保存原始版本
# 如果需要使用修改后的版本，可以：
state_manager.original_dsl_code = None  # 清除原始DSL
# 下次验证时会自动使用UI转换
```

## 注意事项

1. **UI修改不会更新原始DSL**
   - 如果用户在导入后修改了模型，`original_dsl_code` 不会自动更新
   - 这是设计决策：保持原始DSL不变，确保可追溯性
   - 如果需要使用修改后的模型，可以清除 `original_dsl_code`

2. **导出功能不受影响**
   - 导出时仍然使用 `state_manager_to_dsl` 从UI生成DSL
   - 这确保导出的是当前UI状态，而不是原始导入的版本

3. **内存占用**
   - 保存原始DSL会增加一些内存占用
   - 对于大型模型，这个开销是可以接受的

## 未来改进建议

1. **同步机制**
   - 可以考虑在UI修改时标记 `original_dsl_code` 为过期
   - 提供选项让用户选择使用原始版本还是当前UI版本

2. **版本管理**
   - 可以保存多个版本的DSL（原始版本、修改版本）
   - 允许用户在不同版本间切换

3. **差异对比**
   - 提供工具对比原始DSL和当前UI生成的DSL
   - 帮助用户了解做了哪些修改

4. **自动更新选项**
   - 提供配置选项，让用户选择是否在UI修改时自动更新 `original_dsl_code`

## 测试建议

1. **测试导入功能**
   - 验证导入后 `original_dsl_code` 正确保存
   - 验证 `source_file_path` 正确保存

2. **测试验证功能**
   - 使用有原始DSL的模型进行验证
   - 使用没有原始DSL的模型进行验证（fallback）

3. **测试UI修改**
   - 导入模型后修改，验证是否仍使用原始DSL
   - 清除原始DSL后验证，确认使用UI转换

4. **测试边界情况**
   - 空模型
   - 大型复杂模型
   - 包含特殊字符的模型

## 总结

这次重构通过在 `StateManager` 中保存原始DSL代码，实现了更高效、更可靠的验证流程。主要改动集中在模型层和验证相关的对话框，保持了向后兼容性，同时为未来的功能扩展留下了空间。

