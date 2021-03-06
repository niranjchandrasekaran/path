import numpy as np
from parameter.constants import Constant
from math import *
from path.thermo import ThermoDynamics
from tqdm import tqdm


class Time(object):

    def __init__(self):
        pass

    def time_to_transition_state(self, eigenvalue):
        """
        Computes the average force constant and therefore the time to transition state

        :param eigenvalue: Eigenvalue of the hessian
        :return: returns the average force constant and the time to transition state
        """
        if len(eigenvalue) > 6:
            skip = 6
        else:
            skip = 5

        reciprocal = np.reciprocal([eigenvalue[i] for i in range(skip, len(eigenvalue))])

        cumulative = np.cumsum(reciprocal) / np.sum(reciprocal)

        cutoff_id = np.argmin(cumulative < 0.95)

        average_force_constant = 1.0 / (cumulative[cutoff_id] / cutoff_id + 1)

        return 7.0 / average_force_constant, average_force_constant

    def time_steps(self, tbar_left, tbar_right, fc_left, fc_right, energy_left, energy_right, nconf):
        """
        Calculates the time steps at which the intermediate structures have a particular value of energy

        :param tbar_left: time to transition state for the initial state
        :param tbar_right: time to transition state for the final state
        :param fc_left: average force constant of the initial state
        :param fc_right: average force constant of the final state
        :param energy_left: transition state energy relative to the initial state
        :param energy_right: transition state energy relative to the final state
        :param nconf: number of conformations in the trajectory including the end states
        :return: returns the time and energy series for the various conformations in the trajectory
        """
        intermediate = nconf - 2

        step_size = 2.0 / (intermediate + 1)

        ratio = [0]

        current_step_size = step_size

        tf = tbar_left + tbar_right

        for step in range(intermediate):
            if current_step_size >= 1.0:
                ratio.append(2.0 - current_step_size)
            else:
                ratio.append(current_step_size)
            current_step_size += step_size

        ratio.append(0)

        t = []
        energy = []

        for step in range(nconf):
            if step <= nconf / 2:
                if ratio[step] == 0:
                    t.append(0)
                    energy.append(0 + (energy_right - energy_left))
                else:
                    t.append(float(7 + np.log(ratio[step])) / float(fc_left))
                    energy.append(ratio[step]*energy_left + (energy_right - energy_left))
            else:
                if ratio[step] == 0:
                    t.append(tf)
                    energy.append(0)
                else:
                    t.append(tf - (float(7 + np.log(ratio[step])) / float(fc_right)))
                    energy.append(ratio[step]*energy_right)

        return t, energy


class Transition(object):

    def __init__(self, tbar_left, tbar_right, fc_left, fc_right, eval_left, eval_right, evec_left, evec_right,
                 coord_left, coord_right, t_series, natoms):
        """
        Computes the transition state structure and the trajectory

        :param tbar_left: time to transition state for the initial state
        :param tbar_right: time to transition state for the final state
        :param fc_left: average force constant for the initial state
        :param fc_right: average force constant for the final state
        :param eval_left: eigenvalue of the initial state hessian matrix
        :param eval_right: eigenvalue of the final state hessian matrix
        :param evec_left: eigenvector of the initial state hessian matrix
        :param evec_right: eigenvector of the final state hessian matrix
        :param coord_left: coordinates of the initial state
        :param coord_right: coordinates of the final state
        :param t_series: time series of the trajectory
        :param natoms: number of atoms in both the end states
        """
        self.tbar_left = tbar_left
        self.tbar_right = tbar_right
        self.t_series = t_series
        self.tf = self.tbar_left + self.tbar_right

        self.kl = fc_left
        self.kr = fc_right

        self.eval1 = eval_left
        self.eval2 = eval_right

        self.evec1 = evec_left
        self.evec2 = evec_right

        self.coord_left = np.asarray(coord_left).ravel()
        self.coord_right = np.asarray(coord_right).ravel()

        self.natoms = natoms

        self.xbar, self.work_left, self.work_right, self.action_left, self.action_right = self.transition_state()

        self.trajectory_coord = self.trajectory()

    def transition_state(self):
        """
        Computes the transition state and associated parameters
        :return: returns the transition state, work vector relative to both the end states and
        the action relative to the end states
        """
        constant = Constant()
        thermo = ThermoDynamics()

        dimensions = self.natoms * constant.dim

        b_left = [[0 for x in range(dimensions)] for x in range(dimensions)]
        a_right = [[0 for x in range(dimensions)] for x in range(dimensions)]
        s_left = [[0 for x in range(dimensions)] for x in range(dimensions)]
        s_right = [[0 for x in range(dimensions)] for x in range(dimensions)]

        for i in range(dimensions):
            b_left[i][i] = self.eval1[i]
            a_right[i][i] = -self.eval2[i]

        for i in range(dimensions):
            if self.eval1[i] < 0.000001:
                b_left[i][i] = 1.0 / self.tbar_left
                s_left[i][i] = b_left[i][i]
                self.eval1[i] = 0
            elif self.eval1[i] * self.tbar_left < 700 and self.eval1[i] * self.tbar_left > -700:
                b_left[i][i] = self.eval1[i] * cosh(self.eval1[i] * self.tbar_left) / sinh(self.eval1[i] * self.tbar_left)
                s_left[i][i] = self.eval1[i] * exp(self.eval1[i] * self.tbar_left) / sinh(self.eval1[i] * self.tbar_left)
            else:
                pass
            if self.eval2[i] < 0.000001:
                a_right[i][i] = 1 / (self.tbar_left - self.tf)
                s_right[i][i] = -a_right[i][i]
                self.eval2[i] = 0
            elif self.eval2[i] * (self.tbar_left - self.tf) > -700 and self.eval2[i] * (self.tbar_left - self.tf) < 700:
                a_right[i][i] = self.eval2[i] * cosh(self.eval2[i] * (self.tbar_left - self.tf)) / sinh(self.eval2[i] * (self.tbar_left - self.tf))
                s_right[i][i] = self.eval2[i] * exp(self.eval2[i] * (self.tf - self.tbar_left)) / (sinh(self.eval2[i] * (self.tf - self.tbar_left)))
            else:
                pass

        den1 = np.dot(self.evec1, np.dot(b_left, self.evec1.T))
        den2 = np.dot(self.evec2, np.dot(a_right, self.evec2.T))

        num1 = np.dot(den1, self.coord_left)
        num2 = np.dot(den2, self.coord_right)

        num = num1 - num2
        den = den1 - den2

        xbar = np.dot(num, np.linalg.inv(den))

        work_left = np.asarray(thermo.work(xbar, self.coord_left))
        work_right = np.asarray(thermo.work(xbar, self.coord_right))

        s_left_matrix = np.dot(self.evec1, np.dot(s_left, self.evec1.T))
        s_right_matrix = np.dot(self.evec2, np.dot(s_right, self.evec2.T))

        action_left = 0.5 * np.dot(work_left.T, np.dot(s_left_matrix, work_left))
        action_right = 0.5 * np.dot(work_right.T, np.dot(s_right_matrix, work_right))

        return xbar, work_left, work_right, action_left, action_right

    def trajectory(self):
        """
        Computes the transition trajectory
        :return: returns the trajectory
        """
        constant = Constant()
        coord = []
        dimensions = self.natoms * constant.dim

        xlr = [[0 for x in range(dimensions)] for x in range(dimensions)]

        for step in tqdm(range(len(self.t_series))):
            coord.append([])
            for dim in range(dimensions):
                if self.t_series[step] < self.tbar_left:
                    if self.eval1[dim] < 0.000001:
                        xlr[dim][dim] = self.t_series[step] / self.tbar_left
                    else:
                        try:
                            xlr[dim][dim] = sinh(self.eval1[dim] * self.t_series[step]) / sinh(
                                self.eval1[dim] * self.tbar_left)
                        except OverflowError:
                            xlr[dim][dim] = np.exp(self.eval1[dim] * (self.t_series[step] - self.tbar_left))
                else:
                    if self.eval2[dim] < 0.000001:
                        xlr[dim][dim] = (self.tf - self.t_series[step]) / self.tbar_right
                    else:
                        try:
                            xlr[dim][dim] = -sinh(self.eval2[dim] * (self.t_series[step] - self.tf)) / sinh(
                                self.eval2[dim] * self.tbar_right)
                        except OverflowError:
                            xlr[dim][dim] = np.exp(self.eval2[dim] * (self.t_series[step] - self.tf - self.tbar_right))

            if self.t_series[step] < self.tbar_left:
                coord[step] = np.dot(np.dot(self.evec1, np.dot(xlr, self.evec1.T)), self.work_left) + self.coord_left
            else:
                coord[step] = np.dot(np.dot(self.evec2, np.dot(xlr, self.evec2.T)), self.work_right) + self.coord_right

        return np.asarray(coord)
