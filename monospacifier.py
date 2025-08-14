
        Useful to compare a character to others in a font.
        """
        return int(1 + sum(g.width for g in font.glyphs()) / sum(1 for _ in font.glyphs()))

    @staticmethod
    def median_width(font):
        """
        Compute the median character width in FONT.
        Useful to compare a character to others in a font.
        """
        widths = sorted(g.width for g in font.glyphs())
        return int(widths[len(widths) // 2])

    @staticmethod
    def most_common_width(font):
        """
        Find out the most common character width in FONT.
        Useful to determine the width of a monospace font.
        """
        [(width, _)] = Counter(g.width for g in font.glyphs()).most_common(1) # pylint: disable=unbalanced-tuple-unpacking
        return width

    def scale_glyphs(self, scaler):
        """
        Adjust width of glyphs in using SCALER.
        """
        # counter = Counter()
        for glyph in self.font.glyphs():
            scaler.scale(glyph)
            # counter[glyph.width] += 1
        # print("> Final width distribution: {}".format(", ".join(map(str, counter.most_common(10)))))

    def copy_metrics(self, reference):
        for metric in FontScaler.METRICS:
            if hasattr(reference, metric):
                setattr(self.font, metric, getattr(reference, metric))

    def write(self, name):
        """
        Save font to NAME.
        """
        self.font.generate(name)

def plot_widths(glyphs):
    # pylint: disable=unused-variable
    import matplotlib # Putting imports in this order prevents a circular import
    import matplotlib.cbook
    from matplotlib import pyplot

    widths = [glyph.width for glyph in glyphs]
    pyplot.hist(widths, bins=400)
    pyplot.show()

def fname(path):
    return os.path.splitext(os.path.basename(path))[0]

def cleanup_font_name(name, renames):
    name = re.sub('(.monospacified.for.*|-Regular|-Math)', '', name)
    for old, new in renames:
        name = name.replace(old, new)
    return name

def make_monospace(reference, fallback, gscaler, save_to, copy_metrics, renames):
    fontname = "{}_monospacified_for_{}".format(
        cleanup_font_name(fallback.fontname, renames),
        cleanup_font_name(reference.fontname, renames))
    familyname = "{} monospacified for {}".format(
        cleanup_font_name(fallback.familyname, renames),
        cleanup_font_name(reference.familyname, renames))
    fullname = "{} monospacified for {}".format(
        cleanup_font_name(fallback.fullname, renames),
        cleanup_font_name(reference.fullname, renames))

    print("!!! {} !!! {} !!!".format(fallback.fontname, reference.fontname))
    destination = os.path.join(save_to, fontname + ".ttf")
    shutil.copy(fallback.path, destination)
    fscaler = FontScaler(destination)
    fscaler.font.sfnt_names = [] # Get rid of 'Prefered Name' etc.
    fscaler.font.fontname = fontname
    fscaler.font.familyname = familyname
    fscaler.font.fullname = fullname

    fscaler.font.em = reference.em # Adjust em size (number of internal units per em)
    fscaler.scale_glyphs(gscaler)
    if copy_metrics:
        fscaler.copy_metrics(reference)
    fscaler.write(destination)

    return destination

def merge_fonts(reference, fallback, save_to, renames):
    fontname = "{}_extended_with_{}".format(
        cleanup_font_name(reference.fontname, renames),
        cleanup_font_name(fallback.fontname, renames))
    familyname = "{} extended with {}".format(
        cleanup_font_name(reference.familyname, renames),
        cleanup_font_name(fallback.familyname, renames))
    fullname = "{} extended with {}".format(
        cleanup_font_name(reference.fullname, renames),
        cleanup_font_name(fallback.fullname, renames))

    destination = os.path.join(save_to, fontname + ".ttf")
    shutil.copy(reference.path, destination)
    merged = fontforge.open(destination)
    merged.sfnt_names = []
    merged.fontname = fontname
    merged.familyname = familyname
    merged.fullname = fullname

    merged.mergeFonts(fallback.path)
    merged.generate(destination)

    return destination

def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--references', required=True, nargs='+',
                        help="Reference monospace fonts. " +
                        "The metrics (character width, ...) of the newly created monospace fonts are inherited from these.")
    parser.add_argument('--inputs', required=True, nargs='+',
                        help="Variable-width fonts to monospacify.")
    parser.add_argument('--save-to', default=".",
                        help="Where to save the newly generated monospace fonts. Defaults to current directory.")
    parser.add_argument('--merge', action='store_const', const=True, default=False,
                        help="Whether to create copies of the reference font, extended with monospacified glyphs of the inputs.")
    parser.add_argument('--copy-metrics', action='store_const', const=True, default=False,
                        help="Whether to apply the metrics of the reference font to the new font.")
    parser.add_argument('--rename', nargs=2, metavar=("FROM", "TO"), default=[], action="append",
                        help="Replacement to perform in font names (repeat to perform multiple renames)")
    return parser.parse_args()

def process_fonts(ref_paths, fnt_paths, save_to, merge, copy_metrics, renames):
    for ref in ref_paths:
        reference = fontforge.open(ref)
        ref_width = FontScaler.most_common_width(reference)
        print(">>> For reference font {}:".format(reference.familyname))
        for fnt in fnt_paths:
            fallback = fontforge.open(fnt)
            print(">>> - Monospacifying {}".format(fallback.familyname))
            gscaler = StretchingGlyphScaler(ref_width, FontScaler.average_width(fallback))
            path = make_monospace(reference, fallback, gscaler, save_to, copy_metrics, renames)
            if merge:
                monospacified = fontforge.open(path)
                print(">>> - Merging with {}".format(monospacified.familyname))
                path = merge_fonts(reference, monospacified, save_to, renames)
            yield (reference.familyname, fallback.familyname, path)

def main():
    args = parse_arguments()
    results = list(process_fonts(args.references, args.inputs,
                                 args.save_to, args.merge,
                                 args.copy_metrics, args.rename))

    tabdata = {}
    for ref, fnt, ttf in results:
        tabdata.setdefault(u"**{}**".format(ref), []).append(u"[{}]({}?raw=true)".format(fnt, ttf))
    table = [(header, u", ".join(items)) for header, items in sorted(tabdata.items())]

    try:
        from tabulate import tabulate
        print(tabulate(table, headers=[u'Programming font', u'Monospacified fallback fonts'], tablefmt='pipe'))
    except ImportError:
        print("!!! tabulate package not available")

if __name__ == '__main__':
    main()

# Local Variables:
# python-shell-interpreter: "python3"
# End:

