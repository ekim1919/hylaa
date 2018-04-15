'''
Hylaa File I/O Logic
May 2017
Stanley Bak
'''

import numpy as np
from scipy.sparse import csc_matrix

def write_gnuplot(filename, poly_data_dict):
    '''save the polygon data to a file that can be loaded from gnuplot. Sample usage (inside gnuplot):

    file = 'reachable_polys.txt'
    stats file nooutput
    plot for [i=0:STATS_blocks-1] file index i with filledcurves closed
    '''

    with open(filename, 'w') as f:
        f.write('# Reachable State polygons (Code generated by Hylaa using PLOT_GNUPLOT)\n')

        # data
        for _, data in poly_data_dict.iteritems():
            _, _, polys = data

            #[-3, 0; -3, 1; -4, 1; -3.5 0.5;-4, 0]
            for poly in polys:
                f.write("\n")

                for pt in poly:
                    f.write("{} {}\n".format(pt[0], pt[1]))

                f.write("\n")

def write_matlab(filename, poly_data_dict, plot_settings, ha):
    'save the polygon data to a matlab script'

    with open(filename, 'w') as f:

        # header
        f.write('''% Plot reachable region (Code generated by Hylaa using PLOT_MATLAB)
h = figure(1);
set(h, 'Position', [200 200 800 600]);
hold on;

% data
reachSet = [
''')

        # data
        for name, data in poly_data_dict.iteritems():
            fcol, ecol, polys = data
            f.write("    {{'{}', [{} {} {}], [{} {} {}], 0, {{\n".format(name, fcol[0], fcol[1], fcol[2],
                                                                         ecol[0], ecol[1], ecol[2]))

            #[-3, 0; -3, 1; -4, 1; -3.5 0.5;-4, 0]
            for poly in polys:
                f.write("    [")

                for pt in poly:
                    f.write("{}, {};".format(pt[0], pt[1]))

                f.write("]\n")

            f.write("    }}\n")

        f.write('''];

% plot all
for i = 1:size(reachSet,1)
    face_color = reachSet{i,2};
    edge_color = reachSet{i,3};
    poly_list = reachSet{i,5};

    for p_index = 1:size(poly_list,1)
        pts = poly_list{p_index};
        h = fill(pts(:,1), pts(:,2), face_color, 'EdgeColor', edge_color);

        reachSet{i,4} = h;  % add handle to reachSet data structure for use in legend
    end
end

% optional legend
if (size(reachSet,1) > 1 && size(reachSet,1) < 10)
    legend([reachSet{:,3}], reachSet{:,1})
end

% labels and such
''')


        l = plot_settings.label
        x_label = l.x_label if l.x_label is not None else ha.variables[plot_settings.xdim].capitalize()
        y_label = l.y_label if l.y_label is not None else ha.variables[plot_settings.ydim].capitalize()
        title = l.title if l.title is not None else ha.name

        f.write("xlabel('{}', 'FontSize', {}, 'FontName', 'Serif', 'Interpreter','LaTex');\n".format(
            x_label, l.label_size))
        f.write("ylabel('{}', 'FontSize', {}, 'FontName', 'Serif', 'Interpreter','LaTex');\n".format(
            y_label, l.label_size))
        f.write("title('{}', 'FontSize', {}, 'FontName', 'Serif', 'Interpreter','LaTex');\n".format(
            title, l.title_size))

        f.write("hold off;\n")

def write_counter_example(filename, mode, step_size, total_steps, init_pt, init_space_csc, inputs, normal_vec,
                          normal_val, end_val):
    'write a counter-example to a file which can be run using the HyLAA trace generator'

    a_matrix_csc = csc_matrix(mode.a_matrix_csr)
    assert isinstance(normal_vec, np.ndarray)
    assert len(normal_vec.shape) == 1

    with open(filename, 'w') as f:

        f.write('''"Counter-example trace generated using HyLAA"

import sys
from scipy.sparse import csc_matrix, csr_matrix
from hylaa.check_trace import check, plot

def check_instance(stdout=True, skip_plot=False):
    'define parameters for one instance and call checking function'

''')

        dims = a_matrix_csc.shape[0]

        f.write('    data = {}\n'.format([n for n in a_matrix_csc.data]))
        f.write('    indices = {}\n'.format([n for n in a_matrix_csc.indices]))
        f.write('    indptr = {}\n'.format([n for n in a_matrix_csc.indptr]))
        f.write('    a_matrix = csc_matrix((data, indices, indptr), dtype=float, shape=({}, {}))\n'.format(dims, dims))

        ###

        if mode.b_matrix_csc is None:
            f.write('    b_matrix = None\n')
            f.write('    inputs = None\n\n')
        else:
            f.write('    data = {}\n'.format([n for n in mode.b_matrix_csc.data]))
            f.write('    indices = {}\n'.format([n for n in mode.b_matrix_csc.indices]))
            f.write('    indptr = {}\n'.format([n for n in mode.b_matrix_csc.indptr]))
            f.write('    b_matrix = csc_matrix((data, indices, indptr), dtype=float, shape=({}, {}))\n\n'.format(
                mode.b_matrix_csc.shape[0], mode.b_matrix_csc.shape[1]))

            # write inputs to use at each step
            f.write('    inputs = []\n')

            if len(inputs) > 0:
                prev_input = inputs[0]
                total = 1

                for i in xrange(1, len(inputs)):
                    if (inputs[i] == prev_input).all():
                        total += 1
                    else:
                        f.write('    inputs += [{}] * {}\n'.format([u for u in prev_input], total))
                        prev_input = inputs[i]
                        total = 1

                # don't forget the last one
                f.write('    inputs += [{}] * {}\n\n'.format([u for u in prev_input], total))

        ###
        f.write('    step = {}\n'.format(step_size))
        f.write('    max_time = {}\n\n'.format(step_size * total_steps))

        ###

        f.write('    data = {}\n'.format([n for n in init_space_csc.data]))
        f.write('    indices = {}\n'.format([n for n in init_space_csc.indices]))
        f.write('    indptr = {}\n'.format([n for n in init_space_csc.indptr]))
        f.write('    init_space_csc = csc_matrix((data, indices, indptr), dtype=float, shape=({}, {}))\n\n'.format(
            init_space_csc.shape[0], init_space_csc.shape[1]))

        ###

        f.write('    init_point = {}\n'.format([n for n in init_pt]))
        f.write('    start_point = init_space_csc * init_point\n')
        f.write('    normal_vec = {}\n'.format([n for n in normal_vec]))
        f.write('    normal_val = {}\n\n'.format(normal_val))
        f.write('    end_val = {}\n'.format(end_val))

        #####################
        f.write('    sim_states, sim_times, trace_data = check(a_matrix, b_matrix, step, max_time, start_point, ' + \
            'inputs, normal_vec, end_val, stdout=stdout)\n\n')
        f.write('    if not skip_plot and (len(sys.argv) < 2 or sys.argv[1] != "noplot"):\n')
        f.write('        plot(sim_states, sim_times, inputs, normal_vec, normal_val, max_time, step)\n\n')
        f.write('    return trace_data\n\n')

        f.write('if __name__ == "__main__":\n')
        f.write('    check_instance()\n')
