using System;
using System.Collections.Generic;
using System.Linq;
using PChecker.Runtime.Values;

namespace PImplementation
{
    public class tPriorityQueue : IPValue
    {
        private List<ElementWithPriority> elements = new List<ElementWithPriority>();

        public void Add(ElementWithPriority elem)
        {
            elements.Add(elem);
        }

        public IPValue PriorityRemove()
        {
            var removeElem = elements.OrderBy(el => el.Priority).First();
            elements.Remove(removeElem);
            return removeElem.Element;
        }

        public int Size()
        {
            return elements.Count;
        }

        public IPValue GetElementAt(int index)
        {
            return elements.ElementAt(index).Element;
        }

        public bool Equals(IPValue other)
        {
            if (other is tPriorityQueue otherQueue)
            {
                return this.elements.SequenceEqual(otherQueue.elements);
            }
            return false;
        }

        public IPValue Clone()
        {
            var cloned = new tPriorityQueue();
            foreach (var elem in elements)
            {
                cloned.Add(new ElementWithPriority(elem.Element.Clone(), elem.Priority));
            }
            return cloned;
        }
    }

    public class ElementWithPriority
    {
        public IPValue Element { get; }
        public int Priority { get; }

        public ElementWithPriority(IPValue elem, int priority)
        {
            Element = elem;
            Priority = priority;
        }

        public override bool Equals(object obj)
        {
            if (obj is ElementWithPriority other)
            {
                return Element.Equals(other.Element) && Priority == other.Priority;
            }
            return false;
        }

        public override int GetHashCode()
        {
            return Element.GetHashCode() ^ Priority.GetHashCode();
        }
    }
}
