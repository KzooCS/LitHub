#    Copyright 2010, 2011 Kalamazoo College Computer Science Club
#    <kzoo-cs-board@googlegroups.com>

#    This file is part of LitHub.
#
#    LitHub is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    LitHub is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with LitHub.  If not, see <http://www.gnu.org/licenses/>.

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import views as authViews
from django.contrib.auth.models import User
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.template import RequestContext, Context, loader

from datetime import datetime
import isbn

from bookswap.models import Book, Copy
from bookswap.forms import *

def render_403(error, status=403):
    t = loader.get_template('bookswap/error.html')
    c = Context({'error':error,})
    return HttpResponse(t.render(c), status=status)

def book_by_isbn(request, isbn_no):
    try:
        isbn_no = isbn.clean_isbn(isbn_no)
        books = Book.objects.filter(isbn=isbn_no)
        results = [(b, len(b.copy_set.all().filter(soldTime=None))) for b in books]
        results.sort(reverse=True, key=lambda x:x[1])
    except ValueError:
        results = []
    return render(request, "bookswap/book_isbn.html",
            {"results":results})

def book_details(request, book_id):
    book = Book.objects.get(pk=book_id)
    copies = book.copy_set.filter(soldTime=None)
    return render(request, "bookswap/book_copies.html",
        {"book":book, 'copies':copies})

def search_books(request):
    if request.method == "POST":
        if request.POST.get('action') == 'isbn_search':
            isbn_no = request.POST.get("isbn","")
            return redirect('bookswap.views.book_by_isbn', isbn_no=isbn_no)
    title = request.GET.get('title', '')
    author = request.GET.get('author', '')
    if title or author:
        books = Book.objects.filter( title__contains=title,
                author__contains=author)
        results = [(b, len(b.copy_set.filter(soldTime=None))) for b in books]
        results.sort(reverse=True, key=lambda x:x[1])
        return render(request, "bookswap/results.html",
                {"results":results})
    else:
        return render(request, 'bookswap/search.html')

def all_books(request):
    books = Book.objects.all()
    results = [(b, len(b.copy_set.all().filter(soldTime=None))) for b in books]
    results.sort(reverse=True, key=lambda x:x[1])
    return render(request, "bookswap/all_books.html",
            {"results":results})

@login_required
def sell_step_search(request):
    """This step helps identify the book the user is trying to sell"""
    if request.method == "POST":
        isbn_no = request.POST.get('isbn', '')
        try:
            isbn_no = isbn.clean_isbn(isbn_no)
            books = Book.objects.filter(isbn=isbn_no)
            results = [(b, b.copy_set.filter(soldTime=None).count()) \
                    for b in books]
            if results:
                results.sort(reverse=True, key=lambda x:x[1])
                return render(request,
                    "bookswap/sell_select_book.html", 
                    {'results':results, 'isbn_no':isbn_no})
            else:
                return redirect('bookswap.views.sell_new', isbn_no)
        except ValueError:
            messages.error(request, "Invalid ISBN code")
    return render(request, "bookswap/sell_search.html")

@login_required
def sell_existing(request, book_id):
    book = get_object_or_404(Book, pk=book_id)
    form = SellExistingBookForm()
    if request.method == 'POST':
        form = SellExistingBookForm(request.POST)
        if form.is_valid():
            copy = form.save(commit=False)
            copy.book = book
            copy.owner = request.user
            copy.pubDate = datetime.now()
            copy.save()
            messages.success(request, "Your copy of %s is now on sale."%\
                    book.title)
            return redirect('bookswap.views.book_details', book.id)
    return render(request, "bookswap/sell_existing.html",
            {'form':form, 'book':book})

@login_required
def sell_new(request, isbn_no):
    # If an exception is raised at this stage
    # it's not our responsibility to be nice. No well meaning
    # user will see an error page at this stage
    isbn_no = isbn.clean_isbn(isbn_no)
    book_form = SellNewBookForm(prefix="book")
    copy_form = SellExistingBookForm(prefix="copy")
    if request.method == 'POST':
        book_form = SellNewBookForm(request.POST, prefix="book")
        copy_form = SellExistingBookForm(request.POST, prefix="copy")
        if book_form.is_valid() and copy_form.is_valid():
            book = book_form.save(commit=False)
            book.isbn = isbn_no
            book.save()
            copy = copy_form.save(commit=False)
            copy.book = book
            copy.owner = request.user
            copy.pubDate = datetime.now()
            copy.save()
            messages.success(request, "Your copy of %s is now on sale."%\
                    book.title)
            return redirect('bookswap.views.book_details', book.id)
    return render(request, "bookswap/sell_new.html",
            {'book_form':book_form, 'copy_form':copy_form,
                'isbn_no':isbn_no})

@login_required
def my_account(request):
    copies = request.user.copy_set.filter(soldTime=None)
    return render(request, "bookswap/my_account.html",
            {'copies':copies})

@login_required
def mark_sold(request, copy_id):
    copy = Copy.objects.get(pk=copy_id)
    if copy.soldTime != None:
        messages.error("This book is already sold!")
        return redirect('bookswap.views.my_account')
    if copy.owner != request.user:
        messages.error("You may not sell this copy of the book." +\
                " You do not own it.")
        return redirect('bookswap.views.my_account')
    if request.method == 'POST':
        copy.soldTime = datetime.now()
        copy.save()
        messages.success(request, "Your copy was successfully " +\
                "marked as sold. It will no longer be listed " +\
                "publicly on this website.")
        return redirect('bookswap.views.my_account')
    else:
        return render(request, "bookswap/mark_sold.html",
                {'copy':copy})

@login_required
def edit_copy(request, copy_id):
    copy = Copy.objects.get(pk=copy_id)
    if copy.soldTime != None:
        messages.error("This book is already sold!")
        return redirect('bookswap.views.my_account')
    if copy.owner != request.user:
        messages.error("You may not edit this copy." +\
                " You do not own it.")
        return redirect('bookswap.views.my_account')
    form = EditCopyForm(instance=copy)
    if request.method == 'POST':
        form = EditCopyForm(request.POST, instance=copy)
        if form.is_valid():
            copy = form.save()
            messages.success(request, "Your copy of %s was saved" %\
                    copy.book.title)
            return redirect('bookswap.views.my_account')
        else:
            messages.error(request, "There was an error in the form." +\
                    " Please fix the error and try again.")
    return render(request, "bookswap/edit_copy.html",
            {'form':form, 'copy':copy})

@login_required
def view_profile(request, username):
    user = User.objects.get(username=username)
    return render(request, "bookswap/profile_view.html",
            {'user':user})
