/**
 * Admin Table Sorting
 * Lightweight client-side sorting for admin tables
 */

document.addEventListener('DOMContentLoaded', () => {
    const getCellValue = (tr, idx) => tr.children[idx].innerText || tr.children[idx].textContent;

    const comparer = (idx, asc) => (a, b) => ((v1, v2) =>
        v1 !== '' && v2 !== '' && !isNaN(v1) && !isNaN(v2) ? v1 - v2 : v1.toString().localeCompare(v2)
    )(getCellValue(asc ? a : b, idx), getCellValue(asc ? b : a, idx));

    // Handle all tables with class 'admin-table'
    document.querySelectorAll('.admin-table th.sortable').forEach(th => th.addEventListener('click', (() => {
        const table = th.closest('table');
        const tbody = table.querySelector('tbody');

        // Remove active class from other headers
        th.parentElement.querySelectorAll('th').forEach(h => {
            if (h !== th) h.classList.remove('sort-asc', 'sort-desc');
        });

        // Toggle sort order
        const asc = !th.classList.contains('sort-asc');
        th.classList.toggle('sort-asc', asc);
        th.classList.toggle('sort-desc', !asc);

        // Perform sort
        Array.from(tbody.querySelectorAll('tr'))
            .sort(comparer(Array.from(th.parentElement.children).indexOf(th), asc))
            .forEach(tr => tbody.appendChild(tr));
    })));
});
