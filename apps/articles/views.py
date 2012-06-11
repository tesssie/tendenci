from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.contenttypes.models import ContentType
from django.core.urlresolvers import reverse
from django.contrib import messages
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect
from django.template import RequestContext
from django.http import HttpResponseRedirect

from base.http import Http403
from perms.utils import update_perms_and_save, get_notice_recipients, has_perm, get_query_filters, has_view_perm
from site_settings.utils import get_setting
from event_logs.models import EventLog
from meta.models import Meta as MetaTags
from meta.forms import MetaForm
from theme.shortcuts import themed_response as render_to_response
from exports.utils import run_export_task

from articles.models import Article
from articles.forms import ArticleForm
from notification import models as notification


def detail(request, slug=None, template_name="articles/view.html"):
    if not slug:
        return HttpResponseRedirect(reverse('articles'))

    article = get_object_or_404(Article, slug=slug)

    # non-admin can not view the non-active content
    # status=0 has been taken care of in the has_perm function
    if (article.status_detail).lower() != 'active' and (not request.user.profile.is_superuser):
        raise Http403

    if has_view_perm(request.user, 'articles.view_article', article):
        EventLog.objects.log(instance=article)
        return render_to_response(template_name, {'article': article}, 
            context_instance=RequestContext(request))
    else:
        raise Http403


def search(request, template_name="articles/search.html"):
    get = dict(request.GET)
    query = get.pop('q', [])
    get.pop('page', None)  # pop page query string out; page ruins pagination
    query_extra = ['%s:%s' % (k, v[0]) for k, v in get.items() if v[0].strip()]
    query = ' '.join(query)
    if query_extra:
        query = '%s %s' % (query, ' '.join(query_extra))

    if get_setting('site', 'global', 'searchindex') and query:
        articles = Article.objects.search(query, user=request.user)
    else:
        filters = get_query_filters(request.user, 'articles.view_article')
        articles = Article.objects.filter(filters).distinct()
        if not request.user.is_anonymous():
            articles = articles.select_related()

    articles = articles.order_by('-release_dt')

    EventLog.objects.log()

    # Query list of category and subcategory for dropdown filters
    category = request.GET.get('category')
    try:
        category = int(category)
    except:
        category = 0
    categories, sub_categories = Article.objects.get_categories(category=category)

    return render_to_response(template_name, {'articles': articles, 'categories': categories,
        'sub_categories': sub_categories},
        context_instance=RequestContext(request))


def search_redirect(request):
    return HttpResponseRedirect(reverse('articles'))


def print_view(request, slug, template_name="articles/print-view.html"):
    article = get_object_or_404(Article, slug=slug)

    if has_perm(request.user,'articles.view_article', article):
        EventLog.objects.log(instance=article)
        return render_to_response(template_name, {'article': article},
            context_instance=RequestContext(request))
    else:
        raise Http403


@login_required
def edit(request, id, form_class=ArticleForm, template_name="articles/edit.html"):
    article = get_object_or_404(Article, pk=id)

    if has_perm(request.user, 'articles.change_article', article):
        if request.method == "POST":

            form = form_class(request.POST, instance=article, user=request.user)

            if form.is_valid():
                article = form.save(commit=False)

                # update all permissions and save the model
                article = update_perms_and_save(request, form, article)

                messages.add_message(request, messages.SUCCESS, 'Successfully updated %s' % article)

                return HttpResponseRedirect(reverse('article', args=[article.slug]))
        else:
            form = form_class(instance=article, user=request.user)

        return render_to_response(template_name, {'article': article, 'form': form},
            context_instance=RequestContext(request))
    else:
        raise Http403


@login_required
def edit_meta(request, id, form_class=MetaForm, template_name="articles/edit-meta.html"):

    # check permission
    article = get_object_or_404(Article, pk=id)
    if not has_perm(request.user, 'articles.change_article', article):
        raise Http403

    defaults = {
        'title': article.get_title(),
        'description': article.get_description(),
        'keywords': article.get_keywords(),
        'canonical_url': article.get_canonical_url(),
    }
    article.meta = MetaTags(**defaults)

    if request.method == "POST":
        form = form_class(request.POST, instance=article.meta)
        if form.is_valid():
            article.meta = form.save()  # save meta
            article.save()  # save relationship

            messages.add_message(request, messages.SUCCESS, 'Successfully updated meta for %s' % article)

            return HttpResponseRedirect(reverse('article', args=[article.slug]))
    else:
        form = form_class(instance=article.meta)

    return render_to_response(template_name, {'article': article, 'form': form},
        context_instance=RequestContext(request))


@login_required
def add(request, form_class=ArticleForm, template_name="articles/add.html"):
    if has_perm(request.user, 'articles.add_article'):
        if request.method == "POST":
            form = form_class(request.POST, user=request.user)
            if form.is_valid():
                article = form.save(commit=False)

                # add all permissions and save the model
                update_perms_and_save(request, form, article)

                messages.add_message(request, messages.SUCCESS, 'Successfully added %s' % article)

                # send notification to administrator(s) and module recipient(s)
                recipients = get_notice_recipients('module', 'articles', 'articlerecipients')
                if recipients and notification:
                    notification.send_emails(recipients, 'article_added', {
                        'object': article,
                        'request': request,
                    })

                return HttpResponseRedirect(reverse('article', args=[article.slug]))
        else:
            form = form_class(user=request.user)

        return render_to_response(template_name, {'form': form},
            context_instance=RequestContext(request))
    else:
        raise Http403


@login_required
def delete(request, id, template_name="articles/delete.html"):
    article = get_object_or_404(Article, pk=id)

    if has_perm(request.user, 'articles.delete_article'):
        if request.method == "POST":

            messages.add_message(request, messages.SUCCESS, 'Successfully deleted %s' % article)

            # send notification to administrators
            recipients = get_notice_recipients('module', 'articles', 'articlerecipients')
            if recipients:
                if notification:
                    extra_context = {
                        'object': article,
                        'request': request,
                    }
                    notification.send_emails(recipients, 'article_deleted', extra_context)

            article.delete()

            return HttpResponseRedirect(reverse('article.search'))

        return render_to_response(template_name, {'article': article},
            context_instance=RequestContext(request))
    else:
        raise Http403


@staff_member_required
def articles_report(request, template_name='reports/articles.html'):
    article_type = ContentType.objects.get(app_label="articles", model="article")
    stats = EventLog.objects.filter(event_id=435000, content_type=article_type) \
                    .values('content_type', 'object_id', 'headline')\
                    .annotate(count=Count('pk'))\
                    .order_by('-count')

    # get sort order
    sort = request.GET.get('sort', 'viewed')
    if sort == 'viewed':
        stats = stats.order_by('-count')
    elif sort == 'name':
        stats = stats.order_by('headline')
    elif sort == 'created':
        stats = stats.order_by('create_dt')

    for item in stats:

        try:
            article = Article.objects.get(pk=item['object_id'])
            item['article'] = article
            if article.age().days > 0:
                item['per_day'] = item['count'] * 1.0 / article.age().days
            else:
                item['per_day'] = item['count'] * 1.0
        except Article.DoesNotExist:
            pass

    EventLog.objects.log()

    # special sort option
    if sort == 'day':
        stats = sorted(stats, key=lambda item: item['per_day'], reverse=True)

    return render_to_response(template_name, {
        'stats': stats
    }, context_instance=RequestContext(request))


@login_required
def export(request, template_name="articles/export.html"):
    """Export Articles"""

    if not request.user.is_superuser:
        raise Http403

    if request.method == 'POST':
        # initilize initial values
        fields = [
            'guid',
            'slug',
            'timezone',
            'headline',
            'summary',
            'body',
            'source',
            'first_name',
            'last_name',
            'phone',
            'fax',
            'email',
            'website',
            'release_dt',
            'syndicate',
            'featured',
            'design_notes',
            'tags',
            'enclosure_url',
            'enclosure_type',
            'enclosure_length',
            'not_official_content',
            'entity',
        ]
        export_id = run_export_task('articles', 'article', fields)
        return redirect('export.status', export_id)

    return render_to_response(template_name, {
    }, context_instance=RequestContext(request))
