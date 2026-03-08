# Migration from MyLifePathways to YourLifePathways

## Summary
This project was created from the mylifepathways project with all references updated to reflect the new domain: yourlifepathways.com

## Changes Made

### 1. Text Replacements
- All instances of "mylifepathways" → "yourlifepathways"
- All instances of "MyLifePathways" → "YourLifePathways"

### 2. Domain Updates
- www.mylifepathways.com → www.yourlifepathways.com
- All canonical URLs, Open Graph tags, and Twitter card metadata updated

### 3. File Renames
Logo files in static/images/ directory renamed:
- logo_mylifepathways_coaching.png → logo_yourlifepathways_coaching.png
- logo_mylifepathways_coaching.xcf → logo_yourlifepathways_coaching.xcf
- logo_mylifepathways_coaching_horizontal.png → logo_yourlifepathways_coaching_horizontal.png
- logo_mylifepathways_coaching_old.png → logo_yourlifepathways_coaching_old.png
- logo_mylifepathways_coaching_vertical.png → logo_yourlifepathways_coaching_vertical.png
- logo_mylifepathways_coaching_white_background.png → logo_yourlifepathways_coaching_white_background.png

### 4. Files Modified
Updated references in:
- All Python files (*.py)
- All HTML templates (*.html)
- All CSS files (*.css)
- All JavaScript files (*.js)
- All Markdown files (*.md)
- All text files (*.txt)

### 5. Key Files Updated
- templates/base.html - Meta tags, titles, canonical URLs
- templates/index.html - LinkedIn company URL
- templates/blog_detail.html - Schema.org structured data
- index.py - Domain validation and referrer checks
- routes_admin.py - Referrer filtering in admin panels
- routes_blog.py - Meta descriptions and canonical URLs
- routes_main.py - Page titles and sitemap URLs
- README.md - Project structure documentation

## Next Steps

1. **Update LinkedIn Company URL**: Create or update LinkedIn company page for yourlifepathways-coaching
2. **Domain Configuration**: Point yourlifepathways.com domain to hosting
3. **SSL Certificate**: Configure SSL for www.yourlifepathways.com
4. **Environment Variables**: Update any environment-specific configurations
5. **Database**: Review database files (site.db, mylifepathways.db in instance/) - may need renaming
6. **GitHub Repository**: Create new repository for YourLifePathways project
7. **Deployment**: Update deployment configurations (Vercel, Heroku, etc.)

## Notes
- Original git history was removed - this is a fresh repository
- Database files were copied as-is and may need migration
- All functionality should work identically to the original project
