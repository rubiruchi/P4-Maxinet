import json
import argparse
import logging
import os
import sys
import pprint
import random

random.seed(1234)

parser = argparse.ArgumentParser()


parser.add_argument('--nswitches', dest="nswitches", default=2, help = "Mesh size must be even")
parser.add_argument('--nhosts_per_switch', dest="nhosts_per_switch", default=1, help = "Num hosts per switch")
parser.add_argument('--link_delay', dest="link_delay",default=1, help="Link delay")
parser.add_argument('--client_path', dest="client_path", default="python /home/moses/P4-MaxiNet/MaxiNet/WorkerServer/iperf_client.py")
parser.add_argument('--server_path', dest="server_path", default="iperf -s -u -i 0.5 -l 1400B")

args = parser.parse_args()

assert int(args.nswitches) % 2 == 0

nswitches = int(args.nswitches)
nhosts_per_switch = int(args.nhosts_per_switch)
link_delay = int(args.link_delay)

n_hosts = nhosts_per_switch*nswitches

json_data = {}

client_hosts = []
server_hosts = []
all_hosts = []
for i in xrange(1, n_hosts + 1):
	if i % 2 == 1 :
		client_hosts.append(i)
	else:
		server_hosts.append(i)
	all_hosts.append("h" + str(i))

all_switches = {}
for i in xrange(1, nswitches + 1):
	all_switches["s" + str(i)] = {"cli_input" : "s" + str(i) + "-cmnds.txt"}
all_links = []
switches = range(1, nswitches + 1)
for i in switches:
	for j in switches:
		if i != j and j > i:
			all_links.append(["s" + str(i), "s" + str(j), link_delay])

switch_no = 1
num_assigned_hosts = 0
for i in client_hosts :
	if num_assigned_hosts == nhosts_per_switch:
		switch_no += 1
		num_assigned_hosts = 0
	
	all_links.append(["h" + str(i), "s" + str(switch_no), link_delay])
	num_assigned_hosts += 1

switch_no += 1
num_assigned_hosts = 0
for i in server_hosts :
	if num_assigned_hosts == nhosts_per_switch:
		switch_no += 1
		num_assigned_hosts = 0
	
	all_links.append(["h" + str(i), "s" + str(switch_no), link_delay])
	num_assigned_hosts += 1

	 



all_host_cmnds = []

for i in xrange(0, len(client_hosts)) :
	client_host_name = "h" + str(client_hosts[i])
	server_ip = "10.0." + str(server_hosts[i % len(server_hosts)]) + ".10"
	cmd = args.client_path + " " + server_ip
	all_host_cmnds.append([client_host_name, cmd])

for i in xrange(0, len(server_hosts)):
	server_host_name = "h" + str(server_hosts[i])
	cmd = args.server_path
	all_host_cmnds.append([server_host_name, cmd])

json_data["hosts"] = all_hosts
json_data["switches"] = all_switches
json_data["links"] = all_links
json_data["host_cmnds"] = all_host_cmnds
json_data["allowed_paths"] = {}

with open('mesh_topo.json', 'w') as f:
	json.dump(json_data, f, indent=4)


pprint.pprint(json_data)

