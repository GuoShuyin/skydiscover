using System;
using System.Collections.Generic;
using System.Linq;
using PChecker.Runtime;
using PChecker.Runtime.Values;
using PChecker.Runtime.StateMachines;

namespace PImplementation
{
    public static partial class GlobalFunctions
    {
        public static tPriorityQueue CreatePriorityQueue(StateMachine machine)
        {
            return new tPriorityQueue();
        }

        public static tPriorityQueue AddElement(tPriorityQueue queue, IPValue elem, PInt priority, StateMachine machine)
        {
            queue.Add(new ElementWithPriority(elem, priority));
            return queue;
        }

        public static PNamedTuple RemoveElement(tPriorityQueue queue, StateMachine machine)
        {
            var element = queue.PriorityRemove();
            var retVal = new PNamedTuple(new string[] { "element", "queue" }, new IPValue[] { element, queue });
            return retVal;
        }

        public static PInt CountElement(tPriorityQueue queue, StateMachine machine)
        {
            return queue.Size();
        }
    }
}
