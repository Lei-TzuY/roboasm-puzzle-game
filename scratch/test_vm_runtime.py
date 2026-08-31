import json
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from vm import VM


class StubGrid:
    def __init__(self):
        self.width = 2
        self.height = 2
        self.items = {}
        self.inboxes = {}
        self.outboxes = {}
        self.open_doors = set()
        self.ticks = 0

    def tick(self, robots):
        self.ticks += 1


class TestVMRuntime(unittest.TestCase):
    def make_vm(self, instructions):
        return VM(
            instructions,
            StubGrid(),
            [{'x': 0, 'y': 0, 'facing': 'N'}],
        )

    def test_runtime_fault_is_recorded_with_context(self):
        vm = self.make_vm([
            {'opcode': 'MOV', 'args': [8, 'R0'], 'line_num': 1},
            {'opcode': 'DIV', 'args': [0, 'R0'], 'line_num': 2},
        ])

        vm.step()
        vm.step()

        self.assertTrue(vm.halted)
        self.assertEqual(vm.cycles, 2)
        self.assertEqual(len(vm.faults), 1)
        self.assertEqual(vm.last_fault['cycle'], 2)
        self.assertEqual(vm.last_fault['robot_id'], 0)
        self.assertEqual(vm.last_fault['pc'], 1)
        self.assertEqual(vm.last_fault['opcode'], 'DIV')
        self.assertEqual(vm.last_fault['line_num'], 2)
        self.assertIn('Division by zero', vm.last_fault['message'])
        self.assertEqual(vm.robots[0].last_error, vm.last_fault)

    def test_unknown_bytecode_opcode_faults_instead_of_becoming_nop(self):
        vm = self.make_vm([
            {'opcode': 'MVO', 'args': [1, 'R0'], 'line_num': 7},
        ])

        vm.step()

        self.assertTrue(vm.halted)
        self.assertEqual(vm.last_fault['opcode'], 'MVO')
        self.assertIn('Unknown opcode', vm.last_fault['message'])

    def test_malformed_bytecode_operand_faults_before_dispatch(self):
        vm = self.make_vm([
            {'opcode': 'MOV', 'args': [1, 'X'], 'line_num': 4},
        ])

        vm.step()

        self.assertTrue(vm.halted)
        self.assertEqual(vm.last_fault['pc'], 0)
        self.assertIn('must be writable', vm.last_fault['message'])

    def test_runtime_jump_target_is_range_checked(self):
        vm = self.make_vm([
            {'opcode': 'JMP', 'args': [3], 'line_num': 1},
        ])

        vm.step()

        self.assertTrue(vm.halted)
        self.assertIn('outside program range 0..1', vm.last_fault['message'])

    def test_run_stops_at_cycle_budget(self):
        vm = self.make_vm([
            {'opcode': 'JMP', 'args': [0], 'line_num': 1},
        ])

        result = vm.run(max_cycles=5)

        self.assertEqual(result['cycles_executed'], 5)
        self.assertEqual(result['total_cycles'], 5)
        self.assertTrue(result['limit_reached'])
        self.assertFalse(result['halted'])
        self.assertEqual(result['faults'], [])

    def test_run_supports_caller_stop_condition(self):
        vm = self.make_vm([
            {'opcode': 'INC', 'args': ['R0'], 'line_num': 1},
            {'opcode': 'JMP', 'args': [0], 'line_num': 2},
        ])

        result = vm.run(
            max_cycles=20,
            stop_when=lambda current_vm: current_vm.robots[0].registers['R0'] >= 3,
        )

        self.assertTrue(result['stopped_by_condition'])
        self.assertFalse(result['limit_reached'])
        self.assertEqual(vm.robots[0].registers['R0'], 3)
        self.assertEqual(result['cycles_executed'], 5)

    def test_snapshot_is_detached_and_json_serializable(self):
        vm = self.make_vm([
            {'opcode': 'MOV', 'args': [7, 'R0'], 'line_num': 1},
        ])
        vm.shared_ram[4] = 99
        vm.msg_queue.append((0, 12))
        vm.grid.items[(1, 1)] = 5

        snapshot = vm.snapshot()
        json.dumps(snapshot)

        snapshot['robots'][0]['registers']['R0'] = 123
        snapshot['ram'][4] = -1
        snapshot['grid']['items'][0]['value'] = -1

        self.assertEqual(vm.robots[0].registers['R0'], 0)
        self.assertEqual(vm.shared_ram[4], 99)
        self.assertEqual(vm.grid.items[(1, 1)], 5)

    def test_run_can_capture_cycle_by_cycle_trace(self):
        vm = self.make_vm([
            {'opcode': 'MOV', 'args': [1, 'R0'], 'line_num': 1},
            {'opcode': 'INC', 'args': ['R0'], 'line_num': 2},
            {'opcode': 'HLT', 'args': [], 'line_num': 3},
        ])

        result = vm.run(max_cycles=2, capture_trace=True)

        self.assertEqual(result['cycles_executed'], 2)
        self.assertEqual(len(result['trace']), 3)
        self.assertEqual([frame['cycles'] for frame in result['trace']], [0, 1, 2])
        self.assertEqual(
            [frame['robots'][0]['registers']['R0'] for frame in result['trace']],
            [0, 1, 2],
        )
        self.assertTrue(result['limit_reached'])

    def test_run_rejects_invalid_options(self):
        vm = self.make_vm([])
        with self.assertRaises(ValueError):
            vm.run(max_cycles=-1)
        with self.assertRaises(ValueError):
            vm.run(max_cycles=True)
        with self.assertRaises(ValueError):
            vm.run(capture_trace='yes')


if __name__ == '__main__':
    unittest.main()
