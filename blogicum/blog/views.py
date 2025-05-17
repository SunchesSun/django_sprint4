from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Count
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import UpdateView
from .forms import CommentForm, PostForm, UserForm
from .models import Category, Comments, Post, User


PAGINATOR_PAGES = 10


def index(request):
    posts = (
        Post.objects.filter(
            pub_date__lte=timezone.now(),
            is_published=True,
            category__is_published=True
        )
        .annotate(comment_count=Count('comments'))
        .order_by('-pub_date')
    )

    paginator = Paginator(posts, PAGINATOR_PAGES)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {'page_obj': page_obj}
    return render(request, 'blog/index.html', context)


def post_detail(request, id):
    post = get_object_or_404(Post, id=id)

    if post.pub_date > timezone.now():
        if post.author != request.user:
            raise Http404("Публикация ещё не доступна.")

    if not post.is_published and post.author != request.user:
        raise Http404("Публикация недоступна.")

    if not post.category.is_published:
        if post.author != request.user:
            raise Http404('Категория этой публикации скрыта.')

    form = CommentForm()
    context = {
        'post': post,
        'form': form,
        'comments': post.comments.select_related('author')
    }
    return render(request, 'blog/detail.html', context)


def category_posts(request, category_slug):
    category = get_object_or_404(
        Category,
        slug=category_slug,
        is_published=True
    )

    posts = (
        Post.objects.filter(
            category=category,
            is_published=True,
            pub_date__lte=timezone.now()
        )
        .order_by('-pub_date')
        .annotate(comment_count=Count('comments'))
    )
    paginator = Paginator(posts, PAGINATOR_PAGES)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    context = {
        'category': category,
        'page_obj': page_obj,
    }
    return render(request, 'blog/category.html', context)


def profile(request, username):
    user = get_object_or_404(User, username=username)
    if request.user == user:
        posts = Post.objects.filter(author=user).annotate(
            comment_count=Count('comments')
        ).order_by('-pub_date')
    else:
        posts = Post.objects.filter(
            author=user,
            is_published=True,
            category__is_published=True,
            pub_date__lt=timezone.now()
        ).annotate(comments_count=Count('comments')).order_by('-pub_date')
    paginator = Paginator(posts, PAGINATOR_PAGES)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    context = {
        'profile': user,
        'page_obj': page_obj
    }
    return render(request, 'blog/profile.html', context)


@login_required
def create_post(request):
    form = PostForm(
        request.POST or None,
        files=request.FILES or None
    )
    if form.is_valid():
        fields = form.save(commit=False)
        fields.author = request.user
        fields.save()
        return redirect('blog:profile', request.user.username)
    context = {'form': form}
    return render(request, 'blog/create.html', context)


@login_required
def edit_post(request, id):
    post = get_object_or_404(Post, id=id)
    if request.user != post.author:
        return redirect('blog:post_detail', id=id)
    form = PostForm(
        request.POST or None,
        files=request.FILES or None,
        instance=post
    )
    if form.is_valid():
        form.save()
        return redirect('blog:post_detail', id=id)
    context = {'form': form}
    return render(request, 'blog/create.html', context)


@login_required
def delete_post(request, id):
    post = get_object_or_404(Post, id=id)

    if post.author != request.user:
        return redirect('blog:post_detail', id=id)

    if request.method == 'GET':
        form = PostForm(instance=post)
        return render(request, 'blog/create.html', {'form': form})

    if request.method == 'POST':
        post.delete()
        return redirect('blog:profile', username=request.user.username)

    return redirect('blog:post_detail', id=id)


@login_required
def add_comment(request, id):
    post = get_object_or_404(Post, id=id)
    form = CommentForm(request.POST or None)
    if form.is_valid():
        text = form.save(commit=False)
        text.author = request.user
        text.post = post
        text.save()
    return redirect('blog:post_detail', id=id)


@login_required
def edit_comment(request, id, comment_id):
    comment = get_object_or_404(Comments, id=comment_id)
    if request.user != comment.author:
        return redirect('blog:post_detail', id=id)
    form = CommentForm(
        request.POST or None,
        instance=comment
    )
    if form.is_valid():
        form.save()
        return redirect('blog:post_detail', id=id)
    context = {
        'comment': comment,
        'form': form
    }
    return render(request, 'blog/comment.html', context)


@login_required
def delete_comment(request, id, slug):
    comment = get_object_or_404(Comments, id=slug)
    if request.user != comment.author:
        return redirect('blog:post_detail', id=slug)

    if request.method == 'POST':
        comment.delete()
        return redirect('blog:post_detail', id=id)

    if request.method == 'GET':
        context = {'comment': comment}
        return render(request, 'blog/comment.html', context)

    return redirect('blog:post_detail', id=id)


@login_required
def edit_profile(request):
    form = UserForm(
        request.POST or None,
        instance=request.user
    )
    context = {'form': form}
    if form.is_valid():
        form.save()
        return redirect('blog:profile', request.user.username)
    return render(request, 'blog/user.html', context)


class CommentUpdateView(LoginRequiredMixin, UpdateView):
    model = Comments
    fields = ['text']
    context_object_name = 'comment'

    def get_object(self):
        return get_object_or_404(Comments, id=self.kwargs['slug'])

    def dispatch(self, request, *args, **kwargs):
        comment = self.get_object()
        if comment.author != self.request.user:
            return redirect('blog:post_detail', id=self.kwargs['id'])
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse_lazy('blog:post_detail', args=[self.kwargs['id']])
