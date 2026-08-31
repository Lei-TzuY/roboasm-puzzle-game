import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from vm import VM


class StubGrid:
    def __init__(self):
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

    def test_run_rejects_invalid_cycle_budget(self):
        vm = self.make_vm([])
        with self.assertRaises(ValueError):
            vm.run(max_cycles=-1)
        with self.assertRaises(ValueError):
            vm.run(max_cycles=True)


if __name__ == '__main__':
    unittest.main()
