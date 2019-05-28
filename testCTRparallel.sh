#!/bin/bash
export CIRCLE_NODE_TOTAL=4

for (( i = 0; i < $CIRCLE_NODE_TOTAL; i++))
do
	export CIRCLE_NODE_INDEX=`echo $i`
	bash testCTR.sh
done
